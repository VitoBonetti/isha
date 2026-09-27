import os
import io
import pandas as pd
import math
from datetime import date, datetime, timezone
from google.cloud import storage
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from database import SessionLocal
from models.tests import Tests, TestAssets, TestStages, TestRitms, RitmsAndTests
from models.assets import Assets
from models.raw_assets import RawAssets, RawAssetsSnowMetadata
from models.territories import Country
from models.services import ServiceLanes
from audit_logger import log_audit_event, get_bq_client, TABLE_REF
from utils.timeaware import aware_utcnow

# --- Constants & Mappings ---
RITM_BUCKET_NAME = os.environ.get("RITM_BUCKET_NAME")
ARCHIVE_FOLDER = os.environ.get("RITM_BUCKET_ARCHIVE_FOLDER_NAME")

COLUMN_MAPPING = {
    "Number": "id",
    "Stage": "stage",
    "Short description": "description",
    "Requested for": "requested_by",
    "Company": "company",
    "Created": "created",
    "1. OneTrust Asset ID": "onetrust_id",
    "2. Name of the application": "name_app",
    "5. Please provide an estimated date on when you want the pentest to start": "estimated_date",
    "State": "state",
    "Closed": "closed",
    "Closed by": "closed_by",
    "Service Type": "service_requested"
}


# Helpers
def clean_string(val):
    """Strips leading/trailing spaces and converts nan/empty to None."""
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, str):
        cleaned = val.strip()
        return cleaned if cleaned else None
    return val


def parse_datetime(val):
    """Parses standard date times, returns None if empty or invalid."""
    if pd.isna(val) or val == "" or str(val).strip() == "":
        return None
    try:
        # Pandas to_datetime handles variations well, we force UTC
        dt = pd.to_datetime(val)
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def parse_date(val):
    """Parses date-only fields, returns None if empty or invalid."""
    dt = parse_datetime(val)
    if dt:
        return dt.date()
    return None


# Caller
def process_ritm_sync_background(user_id: str, user_role: str):
    """
    Background worker:
    1. Finds the latest RITM Excel sheet in GCS.
    2. Parses and cleans data using Pandas.
    3. Upserts data to PostgreSQL.
    4. Moves the file to the archive folder.
    """
    if not RITM_BUCKET_NAME:
        log_audit_event(user_id, user_role, "RITM_SYNC_FAILED", "SNOW_RITMS", "N/A", "RITM_BUCKET_NAME is not set.")
        return

    client = storage.Client()
    try:
        bucket = client.bucket(RITM_BUCKET_NAME)

        # 1. Find the latest file
        blobs = list(bucket.list_blobs())
        target_blobs = [
            b for b in blobs
            if b.name.startswith("ritm_")
               and b.name.endswith(".xlsx")
               and not b.name.startswith(f"{ARCHIVE_FOLDER}/")
        ]

        if not target_blobs:
            log_audit_event(user_id, user_role, "RITM_SYNC_SKIPPED", "SNOW_RITMS", "N/A",
                            "No new RITM sheets found in bucket.")
            return

        # Sort by name descending (since the timestamp/unicode is in the filename)
        target_blobs.sort(key=lambda x: x.name, reverse=True)
        latest_blob = target_blobs[0]

        # 2. Download and Parse with Pandas
        file_bytes = latest_blob.download_as_bytes()
        df = pd.read_excel(io.BytesIO(file_bytes))

        # Verify required columns exist
        missing_cols = [col for col in COLUMN_MAPPING.keys() if col not in df.columns]
        if missing_cols:
            log_audit_event(user_id, user_role, "RITM_SYNC_FAILED", "SNOW_RITMS", latest_blob.name,
                            f"Missing expected columns: {missing_cols}")
            return

        # Filter only the columns we need and rename them to match our DB schema
        df = df[list(COLUMN_MAPPING.keys())].rename(columns=COLUMN_MAPPING)

        # 3. Clean the data
        records_to_upsert = []
        for _, row in df.iterrows():
            record = {
                "id": clean_string(row.get("id")),
                "stage": clean_string(row.get("stage")) or "N/A",
                "description": clean_string(row.get("description")) or "N/A",
                "requested_by": clean_string(row.get("requested_by")) or "N/A",
                "company": clean_string(row.get("company")) or "N/A",
                "created": parse_datetime(row.get("created")),
                "onetrust_id": clean_string(row.get("onetrust_id")),
                "name_app": clean_string(row.get("name_app")) or "N/A",
                "estimated_date": parse_date(row.get("estimated_date")),
                "state": clean_string(row.get("state")) or "N/A",
                "closed": parse_datetime(row.get("closed")),
                "closed_by": clean_string(row.get("closed_by")),
                "service_requested": clean_string(row.get("service_requested")),
            }
            # Skip if primary key is completely missing
            if record["id"]:
                records_to_upsert.append(record)

        # 4. Upsert into Database
        db = SessionLocal()
        try:
            if records_to_upsert:
                stmt = insert(TestRitms).values(records_to_upsert)

                # Define ON CONFLICT DO UPDATE behavior
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={
                        'stage': stmt.excluded.stage,
                        'description': stmt.excluded.description,
                        'requested_by': stmt.excluded.requested_by,
                        'company': stmt.excluded.company,
                        'created': stmt.excluded.created,
                        'onetrust_id': stmt.excluded.onetrust_id,
                        'name_app': stmt.excluded.name_app,
                        'estimated_date': stmt.excluded.estimated_date,
                        'state': stmt.excluded.state,
                        'closed': stmt.excluded.closed,
                        'closed_by': stmt.excluded.closed_by,
                        'service_requested': stmt.excluded.service_requested,
                    }
                )
                db.execute(stmt)
                db.commit()

            log_audit_event(user_id, user_role, "RITM_SYNC_SUCCESS", "SNOW_RITMS", latest_blob.name,
                            f"Successfully upserted {len(records_to_upsert)} RITMs.")

            match_results = match_tests_with_ritms(db)
            auto_matched_count = match_results["summary"]["total_tests_set_ritm"]

            if auto_matched_count > 0:
                log_audit_event(
                    user_id=user_id,
                    role=user_role,
                    action="RITM_AUTO_MATCH",
                    resource_type="SNOW_RITMS",
                    resource_id="SYSTEM",
                    details=f"Background sync automatically linked {auto_matched_count} tests to RITMs."
                )

        except Exception as e:
            db.rollback()
            log_audit_event(user_id, user_role, "RITM_SYNC_DB_ERROR", "SNOW_RITMS", latest_blob.name,
                            f"Database error during upsert: {str(e)}")
            return  # Stop execution so we don't archive a failed file
        finally:
            db.close()

        # 5. Archive the file
        archive_blob_name = f"{ARCHIVE_FOLDER}/{latest_blob.name}"
        bucket.copy_blob(latest_blob, bucket, archive_blob_name)
        latest_blob.delete()

    except Exception as e:
        log_audit_event(user_id, user_role, "RITM_SYNC_CRASH", "SNOW_RITMS", "N/A",
                        f"Critical crash in background task: {str(e)}")


def get_last_ritm_sync_date():
    client = get_bq_client()
    if not client:
        return {"last_sync": None}

    query = f"""
        SELECT timestamp 
        FROM `{TABLE_REF}` 
        WHERE action = 'RITM_SYNC_SUCCESS' 
        ORDER BY timestamp DESC 
        LIMIT 1
    """
    try:
        results = list(client.query(query).result())
        if results and results[0].timestamp:
            return {"last_sync": results[0].timestamp.isoformat()}
        return {"last_sync": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch last sync from BigQuery: {str(e)}")


def get_filtered_ritms_current_year(
        db: Session,
        page: int = 1,
        limit: int = 100,
        search_id: str = None,
        stage: str = None,
        company: str = None,
        name_app: str = None,
        created_exact: date = None,
        created_from: date = None,
        created_to: date = None,
        estimated_exact: date = None,
        estimated_from: date = None,
        estimated_to: date = None,
        current_year: int = None,
        global_search: str = None,
        sort_by: str = "created"
):

    query = db.query(TestRitms)

    # --- 1. APPLY YEAR FILTER (IF PROVIDED) ---
    # a) Keep if estimated_date is in the current year.
    # b) Keep if estimated_date is NULL AND created is in the current year.
    # (This naturally filters out items created this year but pushed to next year).
    if current_year is not None:
        query = query.filter(
            or_(
                func.extract('year', TestRitms.estimated_date) == current_year,
                and_(
                    TestRitms.estimated_date.is_(None),
                    func.extract('year', TestRitms.created) == current_year
                )
            )
        )

    # c) Exclude Cancelled Stages
    query = query.filter(func.lower(TestRitms.stage) != 'request cancelled')

    # --- 2. APPLY OPTIONAL TEXT FILTERS (ILIKE for partial matches) ---
    if search_id:
        query = query.filter(TestRitms.id.ilike(f"%{search_id}%"))
    if stage:
        query = query.filter(TestRitms.stage.ilike(f"%{stage}%"))
    if company:
        query = query.filter(TestRitms.company.ilike(f"%{company}%"))
    if name_app:
        query = query.filter(TestRitms.name_app.ilike(f"%{name_app}%"))

    if global_search:
        search_term = f"%{global_search}%"
        query = query.filter(
            or_(
                TestRitms.id.ilike(search_term),
                TestRitms.name_app.ilike(search_term),
                TestRitms.company.ilike(search_term),
                TestRitms.onetrust_id.ilike(search_term)
            )
        )

    # --- 3. APPLY OPTIONAL DATE FILTERS ---
    # Created Date (which is a DateTime in DB, so we cast to date for comparison)
    if created_exact:
        query = query.filter(func.date(TestRitms.created) == created_exact)
    if created_from:
        query = query.filter(func.date(TestRitms.created) >= created_from)
    if created_to:
        query = query.filter(func.date(TestRitms.created) <= created_to)

    # Estimated Date (already a Date in DB)
    if estimated_exact:
        query = query.filter(TestRitms.estimated_date == estimated_exact)
    if estimated_from:
        query = query.filter(TestRitms.estimated_date >= estimated_from)
    if estimated_to:
        query = query.filter(TestRitms.estimated_date <= estimated_to)

    # --- 4. CALCULATE METRICS & PAGINATE ---
    total_items = query.count()
    total_pages = math.ceil(total_items / limit) if limit > 0 else 0

    # --- 5. DYNAMIC SORTING ---
    if sort_by == 'name_app':
        query = query.order_by(TestRitms.name_app.asc())
    elif sort_by == 'company':
        query = query.order_by(TestRitms.company.asc())
    elif sort_by == 'id':
        query = query.order_by(TestRitms.id.asc())
    else:
        # Fallback to your original default
        query = query.order_by(TestRitms.created.desc())

    # --- 6. PAGINATE & EXECUTE ---
    results = query.offset((page - 1) * limit).limit(limit).all()

    # Format the payload for the frontend
    items = [{
        "id": r.id,
        "stage": r.stage,
        "description": r.description,
        "requested_by": r.requested_by,
        "company": r.company,
        "created": r.created.isoformat() if r.created else None,
        "onetrust_id": r.onetrust_id,
        "name_app": r.name_app,
        "estimated_date": r.estimated_date.isoformat() if r.estimated_date else None,
        "state": r.state,
        "closed": r.closed.isoformat() if r.closed else None,
        "closed_by": r.closed_by,
        "service_requested": r.service_requested
    } for r in results]

    return {
        "items": items,
        "total_items": total_items,
        "total_pages": total_pages,
        "page": page,
        "limit": limit
    }


def match_tests_with_ritms(db: Session):
    current_year = datetime.now(timezone.utc).year

    # 1. Fetch current-year active tests linked to assets with a valid snow_number
    # Only fetches UNMATCHED tests
    query_assets_tests = (
        db.query(
            RawAssets.id.label("raw_asset_id"),
            RawAssets.name.label("raw_asset_name"),
            RawAssetsSnowMetadata.snow_data['u_onetrust_number'].astext.label("onetrust_id"),
            Tests.id.label("test_id"),
            Tests.name.label("test_name"),
            Country.name.label("country_name"),
            ServiceLanes.name.label("service_name")
        )
        .join(Assets, RawAssets.id == Assets.raw_asset_id)
        .join(TestAssets, Assets.id == TestAssets.asset_id)
        .join(Tests, TestAssets.test_id == Tests.id)
        .outerjoin(RawAssetsSnowMetadata, RawAssets.id == RawAssetsSnowMetadata.correlation_id)
        .outerjoin(Country, RawAssets.country_id == Country.id)
        .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
        .filter(
            Tests.start_year == current_year,
            Tests.stages != TestStages.STOPPED,
            Tests.ritm_matched.isnot(True),
            RawAssets.snow_number.isnot(None),
            RawAssets.snow_number != ''
        )
        .all()
    )

    # 2. Build the asset-to-tests map
    asset_map = {}
    for row in query_assets_tests:
        raw_id_str = str(row.raw_asset_id)
        onetrust_str = str(row.onetrust_id).strip() if row.onetrust_id else None

        if raw_id_str not in asset_map:
            asset_map[raw_id_str] = {
                "name": row.raw_asset_name,
                "uuid": raw_id_str,
                "onetrust_id": onetrust_str,
                "tests": [],
                "ritms": []
            }

        existing_test_ids = {t["uuid"] for t in asset_map[raw_id_str]["tests"]}
        if str(row.test_id) not in existing_test_ids:
            asset_map[raw_id_str]["tests"].append({
                "name": row.test_name,
                "uuid": str(row.test_id),
                "country_name": row.country_name,
                "service_name": row.service_name
            })

    # 3. Fetch current-year RITMs (excluding cancelled)
    current_year_ritms = db.query(TestRitms).filter(
        or_(
            func.extract('year', TestRitms.estimated_date) == current_year,
            and_(
                TestRitms.estimated_date.is_(None),
                func.extract('year', TestRitms.created) == current_year
            )
        ),
        func.lower(TestRitms.stage) != 'request cancelled'
    ).all()

    # Group RITMs by onetrust_id for O(1) lookup
    ritm_by_onetrust = {}
    for r in current_year_ritms:
        if r.onetrust_id:
            clean_ot_id = str(r.onetrust_id).strip()
            if clean_ot_id not in ritm_by_onetrust:
                ritm_by_onetrust[clean_ot_id] = []
            ritm_by_onetrust[clean_ot_id].append(r.id)

    # 4. Perform the matching and track matched RITMs (from THIS execution)
    matched_ritm_ids = set()

    for asset in asset_map.values():
        ot_id = asset["onetrust_id"]
        if ot_id and ot_id in ritm_by_onetrust:
            matching_ritms = ritm_by_onetrust[ot_id]
            asset["ritms"] = matching_ritms
            matched_ritm_ids.update(matching_ritms)

    # 5. Process matches (Auto-Link 1:1) and separate matched/unmatched
    matched_assets = []
    unmatched_tests = []
    total_tests_set_ritm = 0

    for asset in asset_map.values():
        if asset["ritms"]:
            matched_assets.append(asset)

            # --- AUTO-LINKING LOGIC ---
            if len(asset["tests"]) == 1 and len(asset["ritms"]) == 1:
                test_id = asset["tests"][0]["uuid"]
                ritm_id = asset["ritms"][0]

                existing_link = db.query(RitmsAndTests).filter_by(ritm_id=ritm_id, test_id=test_id).first()
                if not existing_link:
                    db.add(RitmsAndTests(ritm_id=ritm_id, test_id=test_id))

                    test_obj = db.query(Tests).filter(Tests.id == test_id).first()
                    if test_obj:
                        test_obj.ritm_matched = True

                    total_tests_set_ritm += 1
        else:
            unmatched_tests.append(asset)

    if total_tests_set_ritm > 0:
        db.commit()

    # --- FIX: Fetch all historically linked RITMs from the database ---
    historically_linked_ritms = db.query(RitmsAndTests.ritm_id).all()
    linked_ritm_id_set = {r[0] for r in historically_linked_ritms}

    # 6. Find RITMs that did not match any asset AND are not already linked in the DB
    unmatched_ritms = [
        {
            "id": r.id,
            "onetrust_id": str(r.onetrust_id).strip() if r.onetrust_id else None,
            "name_app": r.name_app,
            "stage": r.stage,
            "description": r.description,
            "company": r.company
        }
        for r in current_year_ritms
        if r.id not in matched_ritm_ids and r.id not in linked_ritm_id_set
    ]

    return {
        "matched": matched_assets,
        "unmatched_tests": unmatched_tests,
        "unmatched_ritms": unmatched_ritms,
        "summary": {
            "total_matched_assets": len(matched_assets),
            "total_unmatched_tests": len(unmatched_tests),
            "total_unmatched_ritms": len(unmatched_ritms),
            "total_tests_set_ritm": total_tests_set_ritm
        }
    }


def link_test_to_ritm(db: Session, test_id: str, ritm_id: str, current_user: dict):
    # 1. Verify Test exists
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test:
        raise HTTPException(status_code=404, detail="Test not found.")

    # 2. Verify RITM exists
    ritm = db.query(TestRitms).filter(TestRitms.id == ritm_id).first()
    if not ritm:
        raise HTTPException(status_code=404, detail="RITM not found.")

    # 3. Check if they are already linked
    existing_link = db.query(RitmsAndTests).filter_by(ritm_id=ritm_id, test_id=test_id).first()
    if existing_link:
        return {"status": "Success", "message": "Already linked."}

    # 4. Create the link
    new_link = RitmsAndTests(ritm_id=ritm_id, test_id=test_id)
    db.add(new_link)

    # 5. Update the test's matched flag
    test.ritm_matched = True

    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="RITM_MANUAL_LINK",
        resource_type="SNOW_RITMS",
        resource_id=ritm_id,
        details=f"Manually linked Test {test_id} to RITM {ritm_id}."
    )
    return {"status": "Success", "message": "Successfully linked Test to RITM."}


def unlink_test_from_ritm(db: Session, test_id: str, ritm_id: str, current_user: dict):
    # 1. Find the link
    link = db.query(RitmsAndTests).filter_by(ritm_id=ritm_id, test_id=test_id).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link not found.")

    # 2. Delete the link
    db.delete(link)

    # 3. Check if the test has any other RITMs remaining
    remaining_links = db.query(RitmsAndTests).filter_by(test_id=test_id).count()
    if remaining_links == 0:
        test = db.query(Tests).filter(Tests.id == test_id).first()
        if test:
            test.ritm_matched = False

    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="RITM_MANUAL_UNLINK",
        resource_type="SNOW_RITMS",
        resource_id=ritm_id,
        details=f"Manually unlinked Test {test_id} from RITM {ritm_id}."
    )
    return {"status": "Success", "message": "Successfully unlinked Test from RITM."}


def unlink_all_tests_and_ritms(db: Session, current_user: dict):
    try:
        # 1. Delete all links in the junction table
        db.query(RitmsAndTests).delete(synchronize_session=False)

        # 2. Reset the ritm_matched flag on all tests that are currently matched
        db.query(Tests).filter(Tests.ritm_matched == True).update(
            {"ritm_matched": False},
            synchronize_session=False
        )

        db.commit()

        # 3. Log the bulk action
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="RITM_BULK_UNLINK",
            resource_type="SNOW_RITMS",
            resource_id="ALL",
            details="Bulk unlinked all Tests and RITMs and reset matched flags."
        )

        return {"status": "Success", "message": "Successfully unlinked all tests and RITMs."}

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to bulk unlink records: {str(e)}")