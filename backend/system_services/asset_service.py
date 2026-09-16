import uuid
import pandas as pd
import io
from fastapi import HTTPException
from starlette import status
from datetime import datetime
from audit_logger import log_audit_event
from utils.snow_sync import process_and_sync_snow_data, fetch_raw_snow_data
from database import db_cursor_context, SessionLocal
from routers.auth import verify_lane_access
from schema import AssetTypeBase, RawAssetCreate, BulkAssetRequest, BulkServiceUpdateRequest

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB limit
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}


###################################
# ---  VALIDATIONS HELPERS    --- #
###################################
def is_valid_file_signature(contents: bytes, filename: str) -> bool:
    if not contents:
        return False
    ext = filename.lower().split('.')[-1]
    if ext == 'xlsx':
        return contents.startswith(b'\x50\x4B\x03\x04')
    elif ext == 'xls':
        return contents.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1')
    elif ext == 'csv':
        return b'\x00' not in contents[:1024]
    return False


def sanitize_csv_injection(text: str) -> str:
    if not text:
        return text
    if text.startswith(('=', '+', '-', '@')):
        return f"'{text}"
    return text


def insert_asset_history(cursor, raw_asset_id: str, user_id: str, action: str, details: str):
    cursor.execute("""
        INSERT INTO asset_history (id, raw_asset_id, user_id, action, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    """, (str(uuid.uuid4()), raw_asset_id, user_id, action, details))


###################################
# ---      ASSET TYPES        --- #
###################################
def get_all_asset_types(cursor):
    cursor.execute("SELECT id, name FROM asset_types ORDER BY name ASC")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def create_asset_type(cursor, at: AssetTypeBase, current_user: dict):
    new_id = str(uuid.uuid4())
    try:
        cursor.execute("INSERT INTO asset_types (id, name) VALUES (%s, %s)", (new_id, at.name))
        cursor.connection.commit()
        log_audit_event(
            user_id=str(current_user["id"]), role=current_user["role"], action="ASSET_TYPE_CREATE",
            resource_type="ASSETS", resource_id=str(new_id), details=f"Asset Type {at.name} created with ID: {new_id}"
        )
        return {"id": new_id, "message": "Asset Type created."}
    except Exception:
        cursor.connection.rollback()
        raise HTTPException(status_code=400, detail="Asset type name might already exist.")


def update_asset_type(cursor, type_id: str, at: AssetTypeBase, current_user: dict):
    cursor.execute("UPDATE asset_types SET name=%s WHERE id=%s", (at.name, type_id))
    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="ASSET_TYPE_UPDATE",
        resource_type="ASSETS", resource_id=str(type_id), details=f"Asset Type {type_id} has been updated as {at.name} "
    )
    cursor.connection.commit()
    return {"message": "Asset Type updated."}


def delete_asset_type(cursor, type_id: str, current_user: dict):
    cursor.execute("DELETE FROM asset_types WHERE id = %s", (type_id,))
    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="ASSET_TYPE_DELETED",
        resource_type="ASSETS", resource_id=str(type_id), details=f"Asset Type {type_id} has been Deleted "
    )
    cursor.connection.commit()
    return {"message": "Asset Type deleted."}


###################################
# ---      RAW ASSETS         --- #
###################################
def get_paginated_raw_assets(cursor, page, limit, search, country_id, service_id, category_id, asset_type_id,
                             facing_internet, business_critical, status, is_kpi, is_critical, sort_by, sort_dir):
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
    if facing_internet == 'true':
        where_clauses.append("r.facing_internet = true")
    elif facing_internet == 'false':
        where_clauses.append("r.facing_internet = false")
    elif facing_internet == 'null':
        where_clauses.append("r.facing_internet IS NULL")
    if business_critical is not None:
        where_clauses.append("r.business_critical >= %s")
        params.append(business_critical)
    if is_kpi is not None:
        where_clauses.append("r.is_kpi = %s")
        params.append(is_kpi)
    if is_critical is not None:
        where_clauses.append("r.is_critical = %s")
        params.append(is_critical)
    if status == 'raw':
        where_clauses.append("a.id IS NULL")
    elif status == 'pool':
        where_clauses.append("a.id IS NOT NULL")

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    count_query = f"SELECT COUNT(*) FROM raw_assets r LEFT JOIN assets a ON r.id = a.raw_asset_id {where_str}"
    cursor.execute(count_query, tuple(params))
    total_count = cursor.fetchone()[0]

    sort_map = {"name": "r.name", "country": "c.code", "service": "s.name", "category": "cat.name", "type": "at.name",
                "status": "is_promoted"}
    order_col = sort_map.get(sort_by, "r.name")
    order_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    query = f"""
        SELECT r.id, r.name, c.code as country_code, c.name as country_name, s.name as service_name, cat.name as category_name,
               at.name as asset_type_name, r.facing_internet, r.business_critical, r.snow_active,
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


def create_manual_raw_asset(cursor, asset: RawAssetCreate, current_user: dict):
    c_id = str(asset.country_id) if asset.country_id else None
    s_id = str(asset.service_forecast_id) if asset.service_forecast_id else None
    cat_id = str(asset.category_id) if asset.category_id else None
    at_id = str(asset.asset_type_id)

    new_raw_assets_id = str(uuid.uuid4())
    cursor.execute("""
        INSERT INTO raw_assets (
            id, name, description, business_critical, confidentiality_rating, integrity_rating, availability_rating, 
            country_id, service_forecast_id, category_id, asset_type_id, facing_internet, duplicate_allowed, is_kpi, is_critical, create_date
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP) RETURNING id
    """, (
        new_raw_assets_id, asset.name, asset.description, asset.business_critical, asset.confidentiality_rating,
        asset.integrity_rating, asset.availability_rating, c_id, s_id, cat_id, at_id, asset.facing_internet,
        asset.duplicate_allowed, asset.is_kpi, asset.is_critical
    ))

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_CREATED",
        resource_type="RAW_ASSETS", resource_id=str(new_raw_assets_id), details=f"Asset {asset.name} has been created."
    )
    new_id = cursor.fetchone()[0]
    insert_asset_history(cursor, new_id, str(current_user["id"]), "CREATED", "Asset manually added to the system.")
    cursor.connection.commit()
    return {"message": "Raw Asset created", "id": new_id}


def get_single_raw_asset(cursor, raw_id: str, current_user: dict):
    where_clauses = ["r.id = %s"]
    params = [raw_id]

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        if lane_id:
            where_clauses.append("r.service_forecast_id = %s")
            params.append(str(lane_id))
        else:
            where_clauses.append("r.service_forecast_id = '00000000-0000-0000-0000-000000000000'")

    where_str = "WHERE " + " AND ".join(where_clauses)

    cursor.execute(f"""
        SELECT r.id, r.name, r.description, r.business_critical, r.confidentiality_rating, 
            r.integrity_rating, r.availability_rating, r.country_id, r.service_forecast_id, 
            r.category_id, r.asset_type_id, r.facing_internet, r.duplicate_allowed, r.create_date, r.update_date,
            r.snow_number, r.team_note, r.kiss24_asset_id, r.is_kpi, r.is_critical, r.snow_active, m.snow_data,
            CASE WHEN a.id IS NOT NULL THEN true ELSE false END as is_promoted,
            a.is_archived, a.archived_years
        FROM raw_assets r
        LEFT JOIN assets a ON r.id = a.raw_asset_id
        LEFT JOIN raw_assets_snow_metadata m ON r.id = m.correlation_id
        {where_str}
    """, tuple(params))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Asset not found")

    columns = [col[0] for col in cursor.description]
    asset_data = dict(zip(columns, row))

    cursor.execute("""
        SELECT h.id, h.action, h.details, h.timestamp, u.name as user_name
        FROM asset_history h LEFT JOIN users u ON h.user_id = u.id
        WHERE h.raw_asset_id = %s ORDER BY h.timestamp DESC
    """, (raw_id,))
    asset_data["history"] = [dict(zip([col[0] for col in cursor.description], h_row)) for h_row in cursor.fetchall()]

    cursor.execute("""
        SELECT t.id, t.name, t.start_week, t.start_year, sl.name as service_lane, 
            (SELECT string_agg(DISTINCT u.name, ', ') FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = t.id) as pentesters,
            (SELECT timestamp FROM test_history th WHERE th.test_id = t.id AND th.action = 'COMPLETED' ORDER BY timestamp DESC LIMIT 1) as completion_date
        FROM tests t JOIN test_assets ta ON t.id = ta.test_id JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
        WHERE a.raw_asset_id = %s AND t.stages::text = 'COMPLETED' ORDER BY completion_date DESC NULLS LAST
    """, (raw_id,))
    asset_data["completed_tests"] = [dict(zip([col[0] for col in cursor.description], t_row)) for t_row in
                                     cursor.fetchall()]

    return asset_data


def update_raw_asset(cursor, raw_id: str, asset: RawAssetCreate, current_user: dict):
    cursor.execute("""
        SELECT r.name, r.facing_internet, r.duplicate_allowed, r.confidentiality_rating, r.integrity_rating, r.availability_rating,
               c.name as country_name, s.name as service_name, cat.name as category_name, at.name as type_name,
               r.snow_number, r.team_note, r.kiss24_asset_id, r.is_kpi, r.is_critical, r.snow_active, r.service_forecast_id
        FROM raw_assets r
        LEFT JOIN countries c ON r.country_id = c.id
        LEFT JOIN services_lanes s ON r.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON r.category_id = cat.id
        LEFT JOIN asset_types at ON r.asset_type_id = at.id
        WHERE r.id = %s
    """, (raw_id,))
    old_state = cursor.fetchone()
    if not old_state: raise HTTPException(status_code=404, detail="Asset not found")

    old_name, old_internet, old_duplicate_allowed, old_c, old_i, old_a, old_country, old_service, old_category, old_type, old_snow_number, old_team_note, old_kiss24_asset_id, old_is_kpi, old_is_critical, old_snow_active, old_service_id = old_state

    verify_lane_access(current_user, str(old_service_id))
    changes = []

    if current_user.get('role') == 'maintainer':
        cursor.execute(
            "UPDATE raw_assets SET team_note=%s, kiss24_asset_id=%s, update_date=CURRENT_TIMESTAMP WHERE id=%s",
            (asset.team_note, asset.kiss24_asset_id, raw_id))
        if old_team_note != asset.team_note: changes.append(f"Team Note was updated")
        if old_kiss24_asset_id != asset.kiss24_asset_id: changes.append(f"Kiss 24 asset uuid was updated")
    else:
        new_country, new_service, new_category, new_type = "None", "None", "None", "None"
        old_country, old_service, old_category, old_type = old_country or "None", old_service or "None", old_category or "None", old_type or "None"

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

        cursor.execute("""
            UPDATE raw_assets 
            SET name=%s, description=%s, business_critical=%s, confidentiality_rating=%s, integrity_rating=%s, availability_rating=%s, 
                country_id=%s, service_forecast_id=%s, category_id=%s, asset_type_id=%s, facing_internet=%s, duplicate_allowed=%s,
                snow_number=%s, team_note=%s, kiss24_asset_id=%s, is_kpi=%s, is_critical=%s, snow_active=%s, update_date=CURRENT_TIMESTAMP
            WHERE id=%s
        """, (asset.name, asset.description, asset.business_critical, asset.confidentiality_rating,
              asset.integrity_rating, asset.availability_rating, c_id, s_id, cat_id, at_id, asset.facing_internet,
              asset.duplicate_allowed, asset.snow_number, asset.team_note, asset.kiss24_asset_id, asset.is_kpi,
              asset.is_critical, asset.snow_active, raw_id))

        if old_name != asset.name: changes.append(f"Name: '{old_name}' ➔ '{asset.name}'")
        if old_type != new_type: changes.append(f"Type: '{old_type}' ➔ '{new_type}'")
        if old_country != new_country: changes.append(f"Country: '{old_country}' ➔ '{new_country}'")
        if old_service != new_service: changes.append(f"Service: '{old_service}' ➔ '{new_service}'")
        if old_category != new_category: changes.append(f"Category: '{old_category}' ➔ '{new_category}'")
        if old_internet != asset.facing_internet: changes.append(
            f"Internet Facing: {old_internet} ➔ {asset.facing_internet}")
        if old_duplicate_allowed != asset.duplicate_allowed: changes.append(
            f"Allow Duplicates: {old_duplicate_allowed} ➔ {asset.duplicate_allowed}")

    details_str = " | ".join(changes) if changes else "Description Updated."
    insert_asset_history(cursor, raw_id, str(current_user["id"]), "UPDATED", details_str)

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_UPDATED",
        resource_type="RAW_ASSETS", resource_id=str(raw_id),
        details=f"Asset {asset.name} has been updated. ID: {raw_id} "
    )
    cursor.connection.commit()
    return {"message": "Raw Asset updated"}


def delete_raw_asset(cursor, raw_id: str, year: int, current_user: dict):
    cursor.execute('''
        SELECT COUNT(t.id) FROM test_assets ta
        JOIN tests t ON ta.test_id = t.id
        JOIN assets a ON ta.asset_id = a.id
        WHERE a.raw_asset_id = %s AND t.stages::text = 'COMPLETED'
    ''', (str(raw_id),))
    completed_count = cursor.fetchone()[0] or 0

    if completed_count > 0:
        cursor.execute("SELECT archived_years FROM assets WHERE raw_asset_id = %s", (str(raw_id),))
        arr_row = cursor.fetchone()
        current_years = arr_row[0] if arr_row and arr_row[0] else []
        if year not in current_years:
            current_years.append(year)

        cursor.execute("UPDATE assets SET archived_years = %s, is_archived = true WHERE raw_asset_id = %s",
                       (current_years, str(raw_id)))
        insert_asset_history(cursor, str(raw_id), str(current_user["id"]), "ARCHIVED",
                             f"Asset safely archived in {year}.")
        action_msg = f"Asset safely archived to preserve {completed_count} completed tests."
        log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_ARCHIVED",
                        resource_type="RAW_ASSETS", resource_id=str(raw_id), details=f"Asset archived for {year}.")
    else:
        cursor.execute("DELETE FROM raw_assets WHERE id = %s", (str(raw_id),))
        action_msg = "Asset permanently deleted."
        log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_DELETED",
                        resource_type="RAW_ASSETS", resource_id=str(raw_id), details="Asset deleted.")

    cursor.connection.commit()
    return {"message": action_msg}


def restore_raw_asset(cursor, raw_id: str, year: int, current_user: dict):
    cursor.execute("SELECT archived_years FROM assets WHERE raw_asset_id = %s", (str(raw_id),))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Active pool asset not found.")

    current_years = row[0] if row[0] else []
    if year in current_years:
        current_years.remove(year)

    cursor.execute("UPDATE assets SET archived_years = %s, is_archived = false WHERE raw_asset_id = %s",
                   (current_years, str(raw_id)))
    insert_asset_history(cursor, str(raw_id), str(current_user["id"]), "RESTORED",
                         f"Asset restored to the active pool for {year}.")
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_RESTORED",
                    resource_type="RAW_ASSETS", resource_id=str(raw_id), details=f"Asset restored for {year}.")

    cursor.connection.commit()
    return {"message": f"Asset successfully restored for {year}!"}


def bulk_delete_raw_assets(cursor, req: BulkAssetRequest, year: int, current_user: dict):
    deleted_count = 0
    archived_count = 0
    for raw_id in req.raw_asset_ids:
        cursor.execute('''
            SELECT COUNT(t.id) FROM test_assets ta
            JOIN tests t ON ta.test_id = t.id
            JOIN assets a ON ta.asset_id = a.id
            WHERE a.raw_asset_id = %s AND t.stages::text = 'COMPLETED'
        ''', (str(raw_id),))
        completed_count = cursor.fetchone()[0] or 0

        if completed_count > 0:
            cursor.execute("SELECT archived_years FROM assets WHERE raw_asset_id = %s", (str(raw_id),))
            arr_row = cursor.fetchone()
            current_years = arr_row[0] if arr_row and arr_row[0] else []
            if year not in current_years: current_years.append(year)

            cursor.execute("UPDATE assets SET archived_years = %s, is_archived = true WHERE raw_asset_id = %s",
                           (current_years, str(raw_id)))
            insert_asset_history(cursor, str(raw_id), str(current_user["id"]), "ARCHIVED",
                                 f"Asset safely archived in {year}.")
            archived_count += 1
        else:
            cursor.execute("DELETE FROM raw_assets WHERE id = %s", (str(raw_id),))
            deleted_count += 1

    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_BULK_ACTION",
                    resource_type="RAW_ASSETS", resource_id="BULK",
                    details=f"Bulk action: {deleted_count} deleted, {archived_count} archived.")
    cursor.connection.commit()
    return {"message": f"Processed successfully: {deleted_count} deleted, {archived_count} archived."}


###################################
# ---  THE PROMOTION ENGINE   --- #
###################################
def promote_raw_assets_to_pool(cursor, req: BulkAssetRequest, current_user: dict):
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

        insert_asset_history(cursor, str(raw_id), str(current_user["id"]), "PROMOTED",
                             "Asset moved to the Active testing pool.")
        promoted += 1

    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_PROMOTED",
                    resource_type="RAW_ASSETS", resource_id="BULK", details=f"{promoted} assets promoted.")
    cursor.connection.commit()
    return {"message": f"Successfully promoted {promoted} assets to the Active Pool."}


def bulk_update_service_lane(cursor, req: BulkServiceUpdateRequest, current_user: dict):
    service_id = str(req.service_lane_id)
    cursor.execute("SELECT name FROM services_lanes WHERE id = %s", (service_id,))
    s_row = cursor.fetchone()
    s_name = s_row[0] if s_row else "Unknown"

    for asset_id in req.asset_ids:
        cursor.execute("SELECT raw_asset_id FROM assets WHERE id = %s", (str(asset_id),))
        row = cursor.fetchone()
        if not row: continue
        raw_asset_id = str(row[0])

        cursor.execute("UPDATE assets SET service_forecast_id = %s WHERE id = %s", (service_id, str(asset_id)))
        cursor.execute("UPDATE raw_assets SET service_forecast_id = %s, update_date = CURRENT_TIMESTAMP WHERE id = %s",
                       (service_id, raw_asset_id))
        insert_asset_history(cursor, raw_asset_id, str(current_user["id"]), "UPDATED",
                             f"Service Lane bulk updated to '{s_name}'.")

    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"],
                    action="ASSET_UPDATED_SERVICE_LANE_BULK", resource_type="ASSETS", resource_id="BULK",
                    details=f"Bulk updated service lane to {service_id}.")
    cursor.connection.commit()
    return {"message": f"Successfully updated service lane for {len(req.asset_ids)} assets."}


###################################
# ---    ACTIVE ASSET POOL    --- #
###################################
def get_active_asset_pool(cursor, year: int, current_user: dict):
    if current_user['role'] == 'pentester':
        raise HTTPException(status_code=403, detail="Pentesters cannot view the unassigned asset inventory.")

    where_clauses = []
    params = [year, year, year, year]

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        if lane_id:
            where_clauses.append("r.service_forecast_id = %s")
            params.append(str(lane_id))
        else:
            where_clauses.append("r.service_forecast_id = '00000000-0000-0000-0000-000000000000'")

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cursor.execute(f'''
        SELECT a.id, a.raw_asset_id, r.name, r.country_id, c.name as country, s.name as service_name, 
               cat.name as category_name, at.name as asset_type_name, r.duplicate_allowed, r.kiss24_asset_id,
               r.is_kpi, r.is_critical,
            (SELECT COUNT(*) > 0 FROM test_assets ta JOIN tests t ON ta.test_id = t.id WHERE ta.asset_id = a.id AND (t.stages::text = 'NOT_PLANNED' OR (t.stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND t.start_year = %s))) as is_assigned,
            (SELECT COUNT(*) > 0 FROM test_assets ta JOIN tests t ON ta.test_id = t.id WHERE ta.asset_id = a.id AND t.stages::text = 'NOT_PLANNED') as in_backlog,
            (SELECT COUNT(*) FROM test_assets ta JOIN tests t ON ta.test_id = t.id WHERE ta.asset_id = a.id AND t.stages::text = 'COMPLETED' AND t.start_year = %s) as completed_count,
            (a.archived_years IS NOT NULL AND (%s = ANY(a.archived_years) OR (a.is_archived = true AND %s > (SELECT MAX(val) FROM unnest(a.archived_years) as val)))) as is_archived_this_year
        FROM assets a JOIN raw_assets r ON a.raw_asset_id = r.id
        LEFT JOIN countries c ON r.country_id = c.id
        LEFT JOIN services_lanes s ON r.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON r.category_id = cat.id
        LEFT JOIN asset_types at ON r.asset_type_id = at.id
        {where_str}
        ORDER BY r.name ASC
    ''', tuple(params))

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def remove_from_active_pool(cursor, asset_id: str, year: int, current_user: dict):
    cursor.execute("SELECT raw_asset_id, name, archived_years FROM assets WHERE id = %s", (asset_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Asset not found")
    raw_asset_id, asset_name, current_years = str(row[0]), row[1], row[2] or []

    cursor.execute(
        '''SELECT COUNT(t.id) FROM test_assets ta JOIN tests t ON ta.test_id = t.id WHERE ta.asset_id = %s AND t.stages::text = 'COMPLETED' ''',
        (asset_id,))
    completed_count = cursor.fetchone()[0]

    if completed_count > 0:
        if year not in current_years: current_years.append(year)
        cursor.execute("UPDATE assets SET archived_years = %s, is_archived = true WHERE id = %s",
                       (current_years, asset_id))
        action_msg = f"Archived asset for {year} onwards (Preserving {completed_count} completed tests)."
        insert_asset_history(cursor, raw_asset_id, str(current_user["id"]), "ARCHIVED",
                             f"Asset archived from active pool in {year}.")
    else:
        cursor.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
        action_msg = "Asset safely returned to raw data pool."
        insert_asset_history(cursor, raw_asset_id, str(current_user["id"]), "RETURNED",
                             "Asset safely returned to Raw Pool (0 tests).")

    cursor.connection.commit()
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="ASSET_REMOVE_FROM_ACTIVE_POOL",
                    resource_type="ASSETS", resource_id=str(asset_id), details=action_msg)
    return {"message": action_msg}


###################################
# --- ServiceNow integrations --- #
###################################
def full_background_sync_wrapper(user_id: str, user_role: str):
    log_audit_event(user_id=user_id, role=user_role, action="SERVICE_NOW_SYNC_THREAD_START",
                    resource_type="INTEGRATION", details="Background thread launched.")
    try:
        snow_records = fetch_raw_snow_data(user_id, user_role)
        if not snow_records:
            log_audit_event(user_id=user_id, role=user_role, action="SERVICE_NOW_SYNC_CRASH",
                            resource_type="INTEGRATION", details="Fetch returned 0 records. Aborting.")
            return
        db = SessionLocal()
        try:
            process_and_sync_snow_data(db, snow_records, user_id, user_role)
        finally:
            db.close()
    except Exception as e:
        log_audit_event(user_id=user_id, role=user_role, action="SERVICE_NOW_SYNC_CRASH", resource_type="INTEGRATION",
                        details=f"CRITICAL ERROR: {str(e)}")


def process_excel_import_sync(contents: bytes, filename: str, current_user: dict):
    with db_cursor_context() as cursor:
        if not cursor: return 0, ["Database connection unavailable"]
        try:
            df = pd.read_csv(io.BytesIO(contents)) if filename.lower().endswith('.csv') else pd.read_excel(
                io.BytesIO(contents))
            df = df.fillna('')

            cursor.execute("SELECT LOWER(name), id FROM asset_types")
            types_map = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute("SELECT LOWER(name), LOWER(code), id FROM countries")
            countries_map = {name: cid for name, code, cid in cursor.fetchall() if name}
            cursor.execute("SELECT LOWER(name), id FROM services_lanes")
            services_map = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute("SELECT LOWER(name), id FROM service_categories")
            categories_map = {row[0]: row[1] for row in cursor.fetchall()}
            cursor.execute("SELECT id FROM raw_assets")
            existing_ids = {str(row[0]) for row in cursor.fetchall()}

            success_count, failed_items = 0, []

            for _, row in df.iterrows():
                asset_id = sanitize_csv_injection(str(row.get('ID', '')).strip())
                name = sanitize_csv_injection(str(row.get('Name', '')).strip())
                if not name: continue

                type_id = types_map.get(sanitize_csv_injection(str(row.get('Asset Type', '')).strip().lower()))
                country_id = countries_map.get(sanitize_csv_injection(str(row.get('Country', '')).strip().lower()))

                if not type_id or not country_id:
                    failed_items.append(f"{name} (Unknown Type/Country)")
                    continue

                try:
                    new_id = asset_id if asset_id else str(uuid.uuid4())
                    if asset_id and asset_id in existing_ids:
                        cursor.execute("UPDATE raw_assets SET name=%s, update_date=CURRENT_TIMESTAMP WHERE id=%s",
                                       (name, asset_id))
                    else:
                        cursor.execute(
                            "INSERT INTO raw_assets (id, name, country_id, asset_type_id, create_date) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                            (new_id, name, country_id, type_id))
                        existing_ids.add(new_id)
                    success_count += 1
                except Exception:
                    cursor.connection.rollback()
                    failed_items.append(f"{name} (DB Error)")

            cursor.connection.commit()
            return success_count, failed_items
        except Exception as e:
            return 0, [f"File formatting error: {str(e)}"]