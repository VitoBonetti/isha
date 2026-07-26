import os
import requests
from utils.secret_manager import get_secret
from audit_logger import log_audit_event
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy import func
import uuid
from models.raw_assets import RawAssets, RawAssetsSnowMetadata, AssetTypes
from models.territories import Country

SNOW_ENDPOINT = os.environ.get("SNOW_ENDPOINT")
SNOW_SECRET_MANAGER_FILED_NAME = os.environ.get("SNOW_SECRET_MANAGER_FILED_NAME")
SNOW_SECRET_MANAGER_FIELD_PSW = os.environ.get("SNOW_SECRET_MANAGER_FIELD_PSW")
HEADERS = {"Content-Type": "application/json", "Accept": "application/json"}


def extract_app_data(response_json: dict) -> list:
    """
    Extracts explicit fields from the raw ServiceNow CMDB payload structure.
    """
    desired_fields = [
        "u_hosting_locations", "u_implemented_at", "install_type", "number",
        "u_integrity", "active", "u_internet_facing", "last_change_date",
        "short_description", "u_confidentiality", "correlation_id", "asset",
        "support_vendor", "fqdn", "u_hostname", "name",
        "application_type", "u_cloud_platform", "mac_address", "company",
        "u_availability", "ip_address", "u_onetrust_asset_type",
        "u_onetrust_number", "location", "u_cia_total"
    ]

    extracted_data = []

    for item in response_json.get("result", []):
        filtered_item = {}
        for field in desired_fields:
            raw_value = item.get(field)
            # Normalize complex reference object fields down to string values
            if isinstance(raw_value, dict) and 'display_value' in raw_value:
                filtered_item[field] = raw_value.get('display_value')
            else:
                filtered_item[field] = raw_value
        extracted_data.append(filtered_item)

    return extracted_data


def fetch_raw_snow_data(user_id: str, user_role: str) -> list:
    """
    Secures API credentials dynamically and fetches target payloads from ServiceNow in paginated batches.
    """
    snow_user = get_secret(SNOW_SECRET_MANAGER_FILED_NAME)
    snow_password = get_secret(SNOW_SECRET_MANAGER_FIELD_PSW)

    log_audit_event(
        user_id=user_id,
        role=user_role,
        action="SECRET_MANAGER_SNOW_FETCHING",
        resource_type="SECRET_MANAGER",
        resource_id="snow_user/snow_password",
        details="Secrets from ServiceNow have been requested."
    )

    if not snow_user or not snow_password:
        log_audit_event(
            user_id=user_id, role=user_role,
            action="SECRET_MANAGER_SNOW_ERROR",
            resource_type="SECRET_MANAGER", resource_id="snow_user/snow_password",
            details="Sync aborted: Failed to resolve complete API credentials."
        )
        return []

    all_clean_records = []
    limit = 1000
    offset = 0

    try:
        while True:
            print(f"▶️ [SNOW SYNC] Fetching batch: {offset} to {offset + limit}...", flush=True)

            # Using params to safely enforce pagination
            response = requests.get(
                SNOW_ENDPOINT,
                auth=(snow_user, snow_password),
                headers=HEADERS,
                params={"sysparm_limit": limit, "sysparm_offset": offset},
                timeout=(15, 60)
            )

            if response.status_code != 200:
                log_audit_event(
                    user_id=user_id, role=user_role,
                    action="SERVICE_NOW_CONNECTION_FAILED",
                    resource_type="SERVICE_NOW", resource_id=f"{response.status_code}",
                    details=f"ServiceNow connection failure at offset {offset}: HTTP {response.status_code}"
                )
                break

            full_payload = response.json()
            results = full_payload.get("result", [])

            # If the result array is empty, we reached the end of the database!
            if not results:
                break

            clean_chunk = extract_app_data(full_payload)
            all_clean_records.extend(clean_chunk)

            # If we received fewer records than our limit, it means this was the final page
            if len(results) < limit:
                break

            offset += limit  # Move to the next page

        log_audit_event(
            user_id=user_id, role=user_role,
            action="SERVICE_NOW_CONNECTION_SUCCESS",
            resource_type="SERVICE_NOW", resource_id="N/A",
            details=f"Successfully downloaded and filtered a total of {len(all_clean_records)} assets in batches."
        )
        return all_clean_records

    except requests.exceptions.Timeout as e:
        log_audit_event(
            user_id=user_id, role=user_role, action="SERVICE_NOW_CONNECTION_TIMEOUT",
            resource_type="SERVICE_NOW", resource_id=f"{e}",
            details=f"Connection error: The request to ServiceNow timed out during batch {offset}. {e}"
        )
        return all_clean_records  # Return whatever we successfully grabbed before the crash
    except Exception as e:
        log_audit_event(
            user_id=user_id, role=user_role, action="SERVICE_NOW_CONNECTION_ERROR",
            resource_type="SERVICE_NOW", resource_id=f"{e}",
            details=f"Critical error encountered during API fetching cycle: {e}"
        )
        return all_clean_records


def process_and_sync_snow_data(db: Session, snow_records: list, user_id: str, user_role: str):
    """
    Parses ServiceNow records, maps relations in-memory, extracts core fields,
    and safely UPSERTs to raw_assets and raw_assets_snow_metadata.
    """
    if not snow_records:
        log_audit_event(
            user_id=user_id,
            role=user_role,
            action="SERVICE_NOW_SYNC_NO_RECORDS",
            resource_type="SERVICE_NOW",
            resource_id=f"records",
            details=f"No records to process."
        )
        return

    # Create fast lookup dictionaries mapping codes/names to UUIDs
    country_map = {c.code.upper(): c.id for c in db.query(Country).all()}
    asset_type_map = {a.name.lower(): a.id for a in db.query(AssetTypes).all()}

    processed_count = 0
    skipped_count = 0

    for item in snow_records:
        # 1. Ensure we have the correlation_id (Primary Key)
        corr_id_str = item.pop("correlation_id", None)
        if not corr_id_str:
            skipped_count += 1
            continue

        try:
            asset_id = uuid.UUID(corr_id_str)
        except ValueError:
            skipped_count += 1
            continue

        # Country Mapping Logic
        company_str = item.pop("company", "")
        country_code = None

        if company_str:
            if "Global" in company_str:
                country_code = "GIS"
            else:
                # Remove "Randstad ", strip whitespace, uppercase (e.g., "Randstad PT" -> "PT")
                country_code = company_str.replace("Randstad", "").strip().upper()

        country_id = country_map.get(country_code)

        # Asset Type Mapping Logic
        asset_type_str = item.pop("u_onetrust_asset_type", "")
        asset_type_id = asset_type_map.get(asset_type_str.lower() if asset_type_str else "")

        # Strict constraint: If it cannot map to a country or asset type, we must skip it
        # (since these are non-nullable foreign keys in your schema).
        if not country_id or not asset_type_id:
            skipped_count += 1
            continue

        # Extract Core Fields & Cast Types (Item.pop removes them from the dict)
        name = item.pop("name", "Unknown Asset")
        description = item.pop("short_description", None)

        # Safe integer casting for ratings
        def safe_int(val):
            try:
                return int(val) if val else None
            except ValueError:
                return None

        business_critical = safe_int(item.pop("u_cia_total", None))
        confidentiality_rating = safe_int(item.pop("u_confidentiality", None))
        integrity_rating = safe_int(item.pop("u_integrity", None))
        availability_rating = safe_int(item.pop("u_availability", None))

        # Boolean casting
        facing_internet_str = item.pop("u_internet_facing", "")
        facing_internet = True if facing_internet_str and facing_internet_str.lower() == "yes" else False

        # update_date (We leave the string intact or you can parse it to datetime if needed)
        update_date = item.pop("last_change_date", None)

        # UPSERT the Primary Asset (Core Fields)
        # Using PostgreSQL's INSERT ON CONFLICT DO UPDATE
        raw_asset_stmt = insert(RawAssets).values(
            id=asset_id,
            asset_type_id=asset_type_id,
            name=name,
            description=description,
            business_critical=business_critical,
            confidentiality_rating=confidentiality_rating,
            integrity_rating=integrity_rating,
            availability_rating=availability_rating,
            facing_internet=facing_internet,
            country_id=country_id
        )

        # Define what happens if the ID already exists (Update the fields)
        raw_asset_stmt = raw_asset_stmt.on_conflict_do_update(
            index_elements=['id'],
            set_={
                'asset_type_id': raw_asset_stmt.excluded.asset_type_id,
                'name': raw_asset_stmt.excluded.name,
                'description': raw_asset_stmt.excluded.description,
                'business_critical': raw_asset_stmt.excluded.business_critical,
                'confidentiality_rating': raw_asset_stmt.excluded.confidentiality_rating,
                'integrity_rating': raw_asset_stmt.excluded.integrity_rating,
                'availability_rating': raw_asset_stmt.excluded.availability_rating,
                'facing_internet': raw_asset_stmt.excluded.facing_internet,
                'country_id': raw_asset_stmt.excluded.country_id
            }
        )
        db.execute(raw_asset_stmt)

        # UPSERT the Extension Table (Metadata Overflow & Sync Tracking)
        # used .pop() for all core fields, 'item'  contains the leftover SNOW fields!
        snow_meta_stmt = insert(RawAssetsSnowMetadata).values(
            correlation_id=asset_id,
            snow_data=item
        )

        snow_meta_stmt = snow_meta_stmt.on_conflict_do_update(
            index_elements=['correlation_id'],
            set_={
                'snow_data': snow_meta_stmt.excluded.snow_data,
                'last_snow_sync': func.now()  # Updates timestamp automatically
            }
        )
        db.execute(snow_meta_stmt)

        processed_count += 1

    # Commit the massive transaction block
    try:
        # Commit the massive transaction block
        db.commit()
        # db.rollback()  # Reverts to commit this is for testing purpose only
        log_audit_event(
            user_id=user_id,
            role=user_role,
            action="SERVICE_NOW_SYNC_SUCCESS",
            resource_type="SERVICE_NOW",
            resource_id="records",
            details=f"Sync Complete: Processed/Updated {processed_count} assets. Skipped {skipped_count} invalid records."
        )
    except Exception as e:
        db.rollback()  #  Reverts the failed transaction.
        log_audit_event(
            user_id=user_id,
            role=user_role,
            action="SERVICE_NOW_SYNC_CRASH",
            resource_type="SERVICE_NOW",
            resource_id="database",
            details=f"Database commit failed during sync. Rolled back. Error: {str(e)}"
        )