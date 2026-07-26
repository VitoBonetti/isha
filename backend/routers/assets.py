from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Query
from typing import Optional
import pandas as pd
import io
import uuid
import anyio
import sys
from database import get_db_cursor, db_cursor_context, SessionLocal
from routers.auth import get_current_user, require_admin
from schema import RawAssetCreate, AssetBase, PromoteAssetRequest, BulkAssetRequest, AssetTypeBase, BulkServiceUpdateRequest, SnowSyncRequest
from starlette import status
from websockets_manager import manager
from audit_logger import log_audit_event
from utils.snow_sync import process_and_sync_snow_data, fetch_raw_snow_data

router = APIRouter(prefix="/api/assets", tags=["Assets"])

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB limit
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}

#--- VALIDATIONS HELPERS ---
def is_valid_file_signature(contents: bytes, filename: str) -> bool:
    """Validates file contents against expected magic numbers."""
    if not contents:
        return False

    ext = filename.lower().split('.')[-1]

    # XLSX (ZIP format) signature: 50 4B 03 04
    if ext == 'xlsx':
        return contents.startswith(b'\x50\x4B\x03\x04')
    # XLS (OLE2 format) signature: D0 CF 11 E0 A1 B1 1A E1
    elif ext == 'xls':
        return contents.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1')
    # CSV  should not contain binary null bytes
    elif ext == 'csv':
        return b'\x00' not in contents[:1024]

    return False


def sanitize_csv_injection(text: str) -> str:
    """Neutralize executable macros starting with =, +, -, or @ to prevent CSV Injection."""
    if not text:
        return text
    if text.startswith(('=', '+', '-', '@')):
        return f"'{text}"
    return text


# --- ASSET TYPES DICTIONARY ---
@router.get("/types")
def get_asset_types(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT id, name FROM asset_types ORDER BY name ASC")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/types/", summary="[Admin Only]")
def create_asset_type(at: AssetTypeBase, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    new_id = str(uuid.uuid4())
    try:
        cursor.execute("INSERT INTO asset_types (id, name) VALUES (%s, %s)", (new_id, at.name))
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="ASSET_TYPE_CREATE",
            resource_type="ASSETS",
            resource_id=str(new_id),
            details=f"Asset Type {at.name} created with ID: {new_id}",
        )

        return {"id": new_id, "message": "Asset Type created."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=400, detail="Asset type name might already exist.")


@router.put("/types/{type_id}", summary="[Admin Only]")
def update_asset_type(type_id: str, at: AssetTypeBase, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE asset_types SET name=%s WHERE id=%s", (at.name, type_id))

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="ASSET_TYPE_UPDATE",
        resource_type="ASSETS",
        resource_id=str(type_id),
        details=f"Asset Type {type_id} has been updated as {at.name} ",
    )

    cursor.connection.commit()
    return {"message": "Asset Type updated."}


@router.delete("/types/{type_id}", summary="[Admin Only]")
def delete_asset_type(type_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Note: Because of CASCADE rules in DB, this will delete all associated Raw Assets.
    cursor.execute("DELETE FROM asset_types WHERE id = %s", (type_id,))

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="ASSET_TYPE_DELETED",
        resource_type="ASSETS",
        resource_id=str(type_id),
        details=f"Asset Type {type_id} has been Deleted ",
    )

    cursor.connection.commit()
    return {"message": "Asset Type deleted."}


# --- RAW ASSETS ---
@router.get("/raw")
def get_raw_assets(
        page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=500),
        search: Optional[str] = None, country_id: Optional[str] = None,
        service_id: Optional[str] = None, category_id: Optional[str] = None,
        asset_type_id: Optional[str] = None, facing_internet: Optional[bool] = None,
        business_critical: Optional[int] = None, status: Optional[str] = None,
        sort_by: Optional[str] = "name", sort_dir: Optional[str] = "asc",
        current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)
):
    offset = (page - 1) * limit
    params = []
    where_clauses = []

    if search:
        where_clauses.append("r.name ILIKE %s")
        params.append(f"%{search}%")
    if country_id:
        where_clauses.append("r.country_id = %s")
        params.append(country_id)
    if service_id:
        where_clauses.append("r.service_forecast_id = %s")
        params.append(service_id)
    if category_id:
        where_clauses.append("r.category_id = %s")
        params.append(category_id)
    if asset_type_id:
        where_clauses.append("r.asset_type_id = %s")
        params.append(asset_type_id)
    if facing_internet is not None:
        where_clauses.append("r.facing_internet = %s")
        params.append(facing_internet)
    if business_critical is not None:
        where_clauses.append("r.business_critical >= %s")
        params.append(business_critical)

    if status == 'raw':
        where_clauses.append("a.id IS NULL")
    elif status == 'pool':
        where_clauses.append("a.id IS NOT NULL")

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    #  total 4 paginator
    count_query = f"""
            SELECT COUNT(*) FROM raw_assets r
            LEFT JOIN assets a ON r.id = a.raw_asset_id
            {where_str}
        """
    cursor.execute(count_query, tuple(params))
    total_count = cursor.fetchone()[0]

    sort_map = {
        "name": "r.name", "country": "c.code", "service": "s.name",
        "category": "cat.name", "type": "at.name", "status": "is_promoted"
    }
    order_col = sort_map.get(sort_by, "r.name")
    order_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    query = f"""
        SELECT r.id, r.name, c.code as country_code, c.name as country_name, s.name as service_name, cat.name as category_name,
               at.name as asset_type_name, r.facing_internet, r.business_critical,
               CASE WHEN a.id IS NOT NULL THEN true ELSE false END as is_promoted
        FROM raw_assets r
        LEFT JOIN countries c ON r.country_id = c.id
        LEFT JOIN services_lanes s ON r.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON r.category_id = cat.id
        LEFT JOIN asset_types at ON r.asset_type_id = at.id
        LEFT JOIN assets a ON r.id = a.raw_asset_id
        {where_str}
        ORDER BY {order_col} {order_dir}
        LIMIT %s OFFSET %s
    """
    cursor.execute(query, tuple(params + [limit, offset]))
    columns = [col[0] for col in cursor.description]
    items = [dict(zip(columns, row)) for row in cursor.fetchall()]

    return {"items": items, "total_count": total_count}

# --- STANDARDIZED ASSET HISTORY LOGGING ---
def insert_asset_history(cursor, raw_asset_id: str, user_id: str, action: str, details: str):
    """Guarantees a standardized action format and a strict, non-null Database Timestamp."""
    cursor.execute("""
        INSERT INTO asset_history (id, raw_asset_id, user_id, action, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (str(uuid.uuid4()), raw_asset_id, user_id, action, details))


@router.post("/raw", summary="[Admin Only]")
def create_manual_raw_asset(asset: RawAssetCreate, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    c_id = str(asset.country_id) if asset.country_id else None
    s_id = str(asset.service_forecast_id) if asset.service_forecast_id else None
    cat_id = str(asset.category_id) if asset.category_id else None
    at_id = str(asset.asset_type_id)

    new_raw_assets_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO raw_assets (
            id, name, description, business_critical, 
            confidentiality_rating, integrity_rating, availability_rating, 
            country_id, service_forecast_id, category_id, asset_type_id, facing_internet, duplicate_allowed, create_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) RETURNING id
    """, (
        new_raw_assets_id, asset.name, asset.description, asset.business_critical,
        asset.confidentiality_rating, asset.integrity_rating, asset.availability_rating,
        c_id, s_id, cat_id, at_id, asset.facing_internet, asset.duplicate_allowed
    ))

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="RAW_ASSET_CREATED",
        resource_type="RAW_ASSETS",
        resource_id=str(new_raw_assets_id),
        details=f"Asset {asset.name} has been created with ID: {new_raw_assets_id} ",
    )

    new_id = cursor.fetchone()[0]

    # Standardized Creation Log
    insert_asset_history(cursor, new_id, str(current_user["id"]), "CREATED", "Asset manually added to the system.")

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Raw Asset created", "id": new_id}


@router.get("/raw/{raw_id}")
def get_single_raw_asset(raw_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("""
        SELECT r.id, r.name, r.description, r.business_critical, r.confidentiality_rating, 
               r.integrity_rating, r.availability_rating, r.country_id, r.service_forecast_id, 
               r.category_id, r.asset_type_id, r.facing_internet, r.duplicate_allowed, r.create_date, r.update_date,
               CASE WHEN a.id IS NOT NULL THEN true ELSE false END as is_promoted
        FROM raw_assets r
        LEFT JOIN assets a ON r.id = a.raw_asset_id
        WHERE r.id = %s
    """, (raw_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Asset not found")

    columns = [col[0] for col in cursor.description]
    asset_data = dict(zip(columns, row))

    # History
    cursor.execute("""
        SELECT h.id, h.action, h.details, h.timestamp, u.name as user_name
        FROM asset_history h
        LEFT JOIN users u ON h.user_id = u.id
        WHERE h.raw_asset_id = %s
        ORDER BY h.timestamp DESC
    """, (raw_id,))
    hist_cols = [col[0] for col in cursor.description]
    asset_data["history"] = [dict(zip(hist_cols, h_row)) for h_row in cursor.fetchall()]

    # completed tests
    cursor.execute("""
        SELECT t.id, t.name, t.start_week, t.start_year, sl.name as service_lane, 
            (SELECT string_agg(DISTINCT u.name, ', ') FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = t.id) as pentesters,
            (SELECT timestamp FROM test_history th WHERE th.test_id = t.id AND th.action = 'COMPLETED' ORDER BY timestamp DESC LIMIT 1) as completion_date
        FROM tests t
        JOIN test_assets ta ON t.id = ta.test_id
        JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
        WHERE a.raw_asset_id = %s AND t.stages::text = 'COMPLETED'
        ORDER BY completion_date DESC NULLS LAST
    """, (raw_id,))
    tests_cols = [col[0] for col in cursor.description]
    asset_data["completed_tests"] = [dict(zip(tests_cols, t_row)) for t_row in cursor.fetchall()]

    return asset_data


@router.put("/raw/{raw_id}", summary="[Admin Only]")
def update_raw_asset(raw_id: str, asset: RawAssetCreate, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # 1. Fetch the OLD state (including relational names via JOINs)
    cursor.execute("""
        SELECT r.name, r.facing_internet, r.duplicate_allowed, r.confidentiality_rating, r.integrity_rating, r.availability_rating,
               c.name as country_name, s.name as service_name, cat.name as category_name, at.name as type_name
        FROM raw_assets r
        LEFT JOIN countries c ON r.country_id = c.id
        LEFT JOIN services_lanes s ON r.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON r.category_id = cat.id
        LEFT JOIN asset_types at ON r.asset_type_id = at.id
        WHERE r.id = %s
    """, (raw_id,))
    old_state = cursor.fetchone()
    if not old_state:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Unpack old state and handle NULLs gracefully
    old_name, old_internet, old_duplicate_allowed, old_c, old_i, old_a, old_country, old_service, old_category, old_type = old_state
    old_country = old_country or "None"
    old_service = old_service or "None"
    old_category = old_category or "None"
    old_type = old_type or "None"

    # 2. Fetch the NEW state names based on the submitted UUIDs
    new_country, new_service, new_category, new_type = "None", "None", "None", "None"

    c_id = str(asset.country_id) if asset.country_id else None
    s_id = str(asset.service_forecast_id) if asset.service_forecast_id else None
    cat_id = str(asset.category_id) if asset.category_id else None
    at_id = str(asset.asset_type_id) if asset.asset_type_id else None

    if c_id:
        cursor.execute("SELECT name FROM countries WHERE id = %s", (c_id,))
        res = cursor.fetchone()
        if res: new_country = res[0]
    if s_id:
        cursor.execute("SELECT name FROM services_lanes WHERE id = %s", (s_id,))
        res = cursor.fetchone()
        if res: new_service = res[0]
    if cat_id:
        cursor.execute("SELECT name FROM service_categories WHERE id = %s", (cat_id,))
        res = cursor.fetchone()
        if res: new_category = res[0]
    if at_id:
        cursor.execute("SELECT name FROM asset_types WHERE id = %s", (at_id,))
        res = cursor.fetchone()
        if res: new_type = res[0]

    # 3. Perform the Database Update
    cursor.execute("""
        UPDATE raw_assets 
        SET name=%s, description=%s, business_critical=%s, 
            confidentiality_rating=%s, integrity_rating=%s, availability_rating=%s, 
            country_id=%s, service_forecast_id=%s, category_id=%s, asset_type_id=%s, facing_internet=%s, duplicate_allowed=%s,
            update_date=CURRENT_TIMESTAMP
        WHERE id=%s
    """, (
        asset.name, asset.description, asset.business_critical,
        asset.confidentiality_rating, asset.integrity_rating, asset.availability_rating,
        c_id, s_id, cat_id, at_id, asset.facing_internet, asset.duplicate_allowed, raw_id
    ))

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="RAW_ASSET_UPDATED",
        resource_type="RAW_ASSETS",
        resource_id=str(raw_id),
        details=f"Asset {asset.name} has been updated. ID: {raw_id} ",
    )

    # 4. Supercharged Diff Engine
    changes = []
    if old_name != asset.name: changes.append(f"Name: '{old_name}' ➔ '{asset.name}'")
    if old_type != new_type: changes.append(f"Type: '{old_type}' ➔ '{new_type}'")
    if old_country != new_country: changes.append(f"Country: '{old_country}' ➔ '{new_country}'")
    if old_service != new_service: changes.append(f"Service: '{old_service}' ➔ '{new_service}'")
    if old_category != new_category: changes.append(f"Category: '{old_category}' ➔ '{new_category}'")
    if old_internet != asset.facing_internet: changes.append(
        f"Internet Facing: {old_internet} ➔ {asset.facing_internet}")
    if old_duplicate_allowed != asset.duplicate_allowed: changes.append(
        f"Allow Duplicates: {old_duplicate_allowed} ➔ {asset.duplicate_allowed}")
    if old_c != asset.confidentiality_rating: changes.append(f"C-Rating: {old_c} ➔ {asset.confidentiality_rating}")
    if old_i != asset.integrity_rating: changes.append(f"I-Rating: {old_i} ➔ {asset.integrity_rating}")
    if old_a != asset.availability_rating: changes.append(f"A-Rating: {old_a} ➔ {asset.availability_rating}")

    details_str = " | ".join(changes) if changes else "Description Updated."

    # 5. Standardized Update Log
    insert_asset_history(cursor, raw_id, str(current_user["id"]), "UPDATED", details_str)

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Raw Asset updated"}


@router.delete("/raw/{raw_id}", summary="[Admin Only]")
def delete_raw_asset(raw_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM raw_assets WHERE id = %s", (raw_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="RAW_ASSET_DELETED",
        resource_type="RAW_ASSETS",
        resource_id=str(raw_id),
        details=f"Asset with ID: {raw_id}  has been deleted.",
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Asset permanently deleted"}


@router.post("/raw/bulk-delete", summary="[Admin Only]")
def bulk_delete_raw_assets(req: BulkAssetRequest, background_tasks: BackgroundTasks,
                           current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    for raw_id in req.raw_asset_ids:
        cursor.execute("DELETE FROM raw_assets WHERE id = %s", (str(raw_id),))

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="RAW_ASSET_BULK_DELETED",
            resource_type="RAW_ASSETS",
            resource_id=str(raw_id),
            details=f"Asset with ID {raw_id} has been deleted in Bulk Action.",
        )

    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": f"Successfully deleted {len(req.raw_asset_ids)} assets."}


def is_valid_uuid(val: str):
    """Helper to ensure provided CSV IDs are valid UUIDs to prevent DB crashes."""
    try:
        uuid.UUID(str(val))
        return True
    except ValueError:
        return False



# --- SYNCHRONOUS IMPORT IN BACKGROUND THREAD ---
def process_excel_import_sync(contents: bytes, filename: str, current_user: dict):
    with db_cursor_context() as cursor:
        if not cursor: return 0, ["Database connection unavailable"]

        try:
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(io.BytesIO(contents))
            else:
                df = pd.read_excel(io.BytesIO(contents))

            df = df.fillna('')

            cursor.execute("SELECT LOWER(name), id FROM asset_types")
            types_map = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT LOWER(name), LOWER(code), id FROM countries")
            countries_map = {}
            for name, code, cid in cursor.fetchall():
                if name: countries_map[name] = cid
                if code: countries_map[code] = cid

            cursor.execute("SELECT LOWER(name), id FROM services_lanes")
            services_map = {row[0]: row[1] for row in cursor.fetchall()}

            cursor.execute("SELECT LOWER(name), id FROM service_categories")
            categories_map = {row[0]: row[1] for row in cursor.fetchall()}

            # UPDATED: Fetch existing IDs to match against the CSV
            cursor.execute("SELECT id FROM raw_assets")
            existing_ids = {str(row[0]) for row in cursor.fetchall()}

            success_count = 0
            failed_items = []

            for _, row in df.iterrows():
                # Extract and validate ID
                raw_id_str = str(row.get('ID', '')).strip()
                asset_id = sanitize_csv_injection(raw_id_str)

                raw_name = str(row.get('Name', '')).strip()
                if not raw_name: continue
                name = sanitize_csv_injection(raw_name)

                # Validate UUID format if one was provided in the CSV
                if asset_id and not is_valid_uuid(asset_id):
                    failed_items.append(f"{name} (Invalid ID format: Must be a standard UUID)")
                    continue

                raw_desc = str(row.get('Description', '')).strip()
                desc = sanitize_csv_injection(raw_desc)

                raw_type_str = str(row.get('Asset Type', '')).strip().lower()
                type_str = sanitize_csv_injection(raw_type_str)

                raw_country_str = str(row.get('Country', '')).strip().lower()
                country_str = sanitize_csv_injection(raw_country_str)

                raw_service_str = str(row.get('Service Lane', '')).strip().lower()
                service_str = sanitize_csv_injection(raw_service_str)

                raw_cat_str = str(row.get('Category', '')).strip().lower()
                cat_str = sanitize_csv_injection(raw_cat_str)

                raw_internet_val = str(row.get('Facing Internet', '')).strip().lower()
                internet_val = sanitize_csv_injection(raw_internet_val)
                facing_internet = internet_val in ['true', 'yes', '1', 'y']

                try:
                    c_val = int(row.get('Confidentiality', 0))
                    i_val = int(row.get('Integrity', 0))
                    a_val = int(row.get('Availability', 0))
                except ValueError:
                    c_val, i_val, a_val = 0, 0, 0

                business_critical = min(9, c_val + i_val + a_val)

                type_id = types_map.get(type_str)
                country_id = countries_map.get(country_str)
                service_id = services_map.get(service_str) if service_str else None
                cat_id = categories_map.get(cat_str) if cat_str else None

                if not type_id:
                    failed_items.append(f"{name} (Unknown Type: '{type_str}')")
                    continue
                if not country_id:
                    failed_items.append(f"{name} (Unknown Country: '{country_str}')")
                    continue

                try:
                    # UPSERT LOGIC VIA ID
                    if asset_id and asset_id in existing_ids:
                        # UPDATE: Now updates Name and Country too, since ID is the anchor
                        cursor.execute("""
                            UPDATE raw_assets SET name=%s, description=%s, business_critical=%s, 
                            confidentiality_rating=%s, integrity_rating=%s, availability_rating=%s, 
                            country_id=%s, service_forecast_id=%s, category_id=%s, asset_type_id=%s, facing_internet=%s,
                            update_date=CURRENT_TIMESTAMP
                            WHERE id=%s
                        """,
                                       (name, desc, business_critical, c_val, i_val, a_val, country_id, service_id,
                                        cat_id, type_id, facing_internet, asset_id))
                        insert_asset_history(cursor, asset_id, str(current_user["id"]), "IMPORTED",
                                             "Asset metadata updated via bulk Excel import.")
                    else:
                        # INSERT: Use provided ID, or generate a new one if blank
                        new_id = asset_id if asset_id else str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO raw_assets (
                                id, name, description, business_critical, 
                                confidentiality_rating, integrity_rating, availability_rating, 
                                country_id, service_forecast_id, category_id, asset_type_id, facing_internet, create_date
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
                        """, (new_id, name, desc, business_critical, c_val, i_val, a_val, country_id, service_id,
                              cat_id, type_id, facing_internet))

                        insert_asset_history(cursor, new_id, str(current_user["id"]), "IMPORTED",
                                             "Asset created via bulk Excel import.")

                        # Add new ID to the tracking set so subsequent rows in this same file don't duplicate
                        existing_ids.add(new_id)

                    success_count += 1
                except Exception:
                    cursor.connection.rollback()
                    failed_items.append(f"{name} (DB Error)")

            cursor.connection.commit()

            if failed_items:
                log_audit_event(
                    user_id=str(current_user["id"]), role=current_user["role"],
                    action="IMPORT_WARNINGS",
                    resource_type="ASSETS",
                    resource_id="N/A",
                    details=f"Failed to import {len(failed_items)} rows: {', '.join(failed_items[:10])}{'...' if len(failed_items) > 10 else ''}"
                )

            return success_count, failed_items

        except Exception as e:
            return 0, [f"File formatting error: {str(e)}"]


@router.post("/raw/import", summary="[Admin Only]")
async def import_assets(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(), current_user: dict = Depends(require_admin)):
    # Mime type validations
    if file.content_type not in ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File type not allowed")
    # enforcing 5 MB limit
    contents = b""
    while chunk := await file.read(1024 * 1024): # chunck of 1 MB
        contents += chunk
        if len(contents) > MAX_FILE_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")
    # Signature Check
    if not is_valid_file_signature(contents, file.filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file signature")

    # anyio.to_thread runs the synchronous parsing/DB operations in a background worker thread
    # This prevents the FastAPI event loop from freezing, keeping WebSockets responsive!
    success_count, failed_items = await anyio.to_thread.run_sync(
        process_excel_import_sync, contents, file.filename, current_user
    )

    if success_count > 0:
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')

    return {
        "message": "Import processed",
        "success": success_count,
        "failed": failed_items
    }


# --- THE PROMOTION ENGINE ---
@router.post("/promote", summary="[Admin Only]")
def promote_raw_assets_to_pool(req: BulkAssetRequest, background_tasks: BackgroundTasks,
                               current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    promoted = 0
    for raw_id in req.raw_asset_ids:
        cursor.execute("SELECT id FROM assets WHERE raw_asset_id = %s", (str(raw_id),))
        if cursor.fetchone(): continue

        cursor.execute(
            "SELECT name, country_id, service_forecast_id, category_id, asset_type_id FROM raw_assets WHERE id = %s",
            (str(raw_id),))
        raw_data = cursor.fetchone()
        if not raw_data: continue

        new_promote_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO assets (id, raw_asset_id, name, country_id, service_forecast_id, category_id, asset_type_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (new_promote_id, str(raw_id), raw_data[0], raw_data[1], raw_data[2], raw_data[3], raw_data[4]))

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="RAW_ASSET_PROMOTED",
            resource_type="RAW_ASSETS",
            resource_id=str(raw_id),
            details=f"Asset {raw_data[0]} with ID: {raw_id} has been promoted. Test ID: {new_promote_id} ",
        )

        # Standardized Promotion Log
        insert_asset_history(cursor, str(raw_id), str(current_user["id"]), "PROMOTED",
                             "Asset moved to the Active testing pool.")

        promoted += 1

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": f"Successfully promoted {promoted} assets to the Active Pool."}


@router.put("/bulk-service", summary="[Admin Only]")
def bulk_update_service_lane(req: BulkServiceUpdateRequest, background_tasks: BackgroundTasks,
                             current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    service_id = str(req.service_lane_id)

    # Fetch new service name for logging
    cursor.execute("SELECT name FROM services_lanes WHERE id = %s", (service_id,))
    s_row = cursor.fetchone()
    s_name = s_row[0] if s_row else "Unknown"

    for asset_id in req.asset_ids:
        # Get raw_asset_id linked to this pool asset
        cursor.execute("SELECT raw_asset_id FROM assets WHERE id = %s", (str(asset_id),))
        row = cursor.fetchone()
        if not row: continue
        raw_asset_id = str(row[0])

        # 1. Update the Active Pool record
        cursor.execute("UPDATE assets SET service_forecast_id = %s WHERE id = %s", (service_id, str(asset_id)))

        # 2. Update the Source Raw record permanently
        cursor.execute("UPDATE raw_assets SET service_forecast_id = %s, update_date = CURRENT_TIMESTAMP WHERE id = %s",
                       (service_id, raw_asset_id))

        # 3. Log it in the Asset's History
        insert_asset_history(cursor, raw_asset_id, str(current_user["id"]), "UPDATED",
                             f"Service Lane bulk updated to '{s_name}'.")

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="ASSET_UPDATED_SERVICE_LANE_BULK",
            resource_type="ASSETS",
            resource_id=str(asset_id),
            details=f"Service Lane with ID: {service_id} has been set to Asset ID: {asset_id} in a Bulk Action. ",
        )

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": f"Successfully updated service lane for {len(req.asset_ids)} assets."}


# --- ACTIVE ASSET POOL ---
@router.get("/")
def get_active_asset_pool(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user['role'] == 'pentester':
        raise HTTPException(status_code=403, detail="Pentesters cannot view the unassigned asset inventory.")

    cursor.execute('''
        SELECT a.id, 
               a.raw_asset_id, 
               r.name, 
               c.name as country, 
               s.name as service_name, 
               cat.name as category_name, 
               at.name as asset_type_name, 
               r.duplicate_allowed,
               (
                   SELECT COUNT(*) > 0 
                   FROM test_assets ta 
                   JOIN tests t ON ta.test_id = t.id 
                   WHERE ta.asset_id = a.id 
                     AND t.stages::text IN ('NOT_PLANNED', 'SCHEDULED', 'IN_PROGRESS')
               ) as is_assigned,
               (
                   SELECT COUNT(*)
                   FROM test_assets ta
                   JOIN tests t ON ta.test_id = t.id
                   WHERE ta.asset_id = a.id AND t.stages::text = 'COMPLETED'
               ) as completed_count
        FROM assets a
        JOIN raw_assets r ON a.raw_asset_id = r.id
        LEFT JOIN countries c ON r.country_id = c.id
        LEFT JOIN services_lanes s ON r.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON r.category_id = cat.id
        LEFT JOIN asset_types at ON r.asset_type_id = at.id
        ORDER BY r.name ASC
    ''')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.delete("/{asset_id}", summary="[Admin Only]")
def remove_from_active_pool(asset_id: str, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="ASSET_REMOVE_FROM_ACTIVE_POOL",
        resource_type="ASSETS",
        resource_id=str(asset_id),
        details=f"Asset with ID: {asset_id} has been removed from active pool. ",
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Asset returned to raw data pool."}


# Service Now integrations
def full_background_sync_wrapper(user_id: str, user_role: str):
    """Wrapper to run the ENTIRE fetch and sync process in the background."""

    # 1. Force a log to BigQuery so it appears on your frontend terminal instantly
    log_audit_event(
        user_id=user_id,
        role=user_role,
        action="SERVICE_NOW_SYNC_THREAD_START",
        resource_type="INTEGRATION",
        details="Background thread successfully launched. Fetching API data..."
    )

    try:
        # Fetch the data in the background
        snow_records = fetch_raw_snow_data(user_id, user_role)

        if not snow_records:
            log_audit_event(
                user_id=user_id, role=user_role,
                action="SERVICE_NOW_SYNC_CRASH",
                resource_type="INTEGRATION",
                details="Fetch returned 0 records or failed. Aborting."
            )
            return

        # Process and save to DB
        db = SessionLocal()
        try:
            process_and_sync_snow_data(db, snow_records, user_id, user_role)
        finally:
            db.close()

    except Exception as e:
        # Catch any catastrophic Python crashes and log them to your UI
        log_audit_event(
            user_id=user_id,
            role=user_role,
            action="SERVICE_NOW_SYNC_CRASH",
            resource_type="INTEGRATION",
            details=f"CRITICAL ERROR IN BACKGROUND THREAD: {str(e)}"
        )


@router.post("/servicenow", summary="[Admin Only]")
def trigger_snow_sync(
        payload: SnowSyncRequest,
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_admin)
):
    # Hand off ALL heavy lifting to FastAPI's background thread
    background_tasks.add_task(
        full_background_sync_wrapper,
        str(current_user["id"]),
        str(current_user["role"])
    )

    # Log that the admin initiated it
    log_audit_event(
        user_id=str(current_user["id"]),
        role=str(current_user["role"]),
        action="SNOW_SYNC_STARTED",
        resource_type="INTEGRATION",
        details="Admin manually triggered the ServiceNow CMDB sync."
    )

    return {"message": "ServiceNow sync started in the background. This may take a few minutes."}