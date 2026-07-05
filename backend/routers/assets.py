from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Query
from typing import Optional
import pandas as pd
import io
import uuid
import anyio
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin
from schema import RawAssetCreate, AssetBase, PromoteAssetRequest, BulkAssetRequest
from websockets_manager import manager
from audit_logger import log_audit_event

router = APIRouter(prefix="/api/assets", tags=["Assets"])


# --- ASSET TYPES DICTIONARY ---
@router.get("/types")
def get_asset_types(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT id, name FROM asset_types ORDER BY name ASC")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


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
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/raw")
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
            country_id, service_forecast_id, category_id, asset_type_id, facing_internet
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (
        new_raw_assets_id, asset.name, asset.description, asset.business_critical,
        asset.confidentiality_rating, asset.integrity_rating, asset.availability_rating,
        c_id, s_id, cat_id, at_id, asset.facing_internet
    ))
    new_id = cursor.fetchone()[0]
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Raw Asset created", "id": new_id}


@router.get("/raw/{raw_id}")
def get_single_raw_asset(raw_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("""
        SELECT r.id, r.name, r.description, r.business_critical, r.confidentiality_rating, 
               r.integrity_rating, r.availability_rating, r.country_id, r.service_forecast_id, 
               r.category_id, r.asset_type_id, r.facing_internet,
               CASE WHEN a.id IS NOT NULL THEN true ELSE false END as is_promoted
        FROM raw_assets r
        LEFT JOIN assets a ON r.id = a.raw_asset_id
        WHERE r.id = %s
    """, (raw_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Asset not found")
    columns = [col[0] for col in cursor.description]
    return dict(zip(columns, row))


@router.put("/raw/{raw_id}")
def update_raw_asset(raw_id: str, asset: RawAssetCreate, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    c_id = str(asset.country_id) if asset.country_id else None
    s_id = str(asset.service_forecast_id) if asset.service_forecast_id else None
    cat_id = str(asset.category_id) if asset.category_id else None
    at_id = str(asset.asset_type_id)

    cursor.execute("""
        UPDATE raw_assets 
        SET name=%s, description=%s, business_critical=%s, 
            confidentiality_rating=%s, integrity_rating=%s, availability_rating=%s, 
            country_id=%s, service_forecast_id=%s, category_id=%s, asset_type_id=%s, facing_internet=%s
        WHERE id=%s
    """, (
        asset.name, asset.description, asset.business_critical,
        asset.confidentiality_rating, asset.integrity_rating, asset.availability_rating,
        c_id, s_id, cat_id, at_id, asset.facing_internet, raw_id
    ))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Raw Asset updated"}


@router.delete("/raw/{raw_id}")
def delete_raw_asset(raw_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM raw_assets WHERE id = %s", (raw_id,))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Asset permanently deleted"}


@router.post("/raw/bulk-delete")
def bulk_delete_raw_assets(req: BulkAssetRequest, background_tasks: BackgroundTasks,
                           current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    for raw_id in req.raw_asset_ids:
        cursor.execute("DELETE FROM raw_assets WHERE id = %s", (str(raw_id),))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": f"Successfully deleted {len(req.raw_asset_ids)} assets."}


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

            cursor.execute("SELECT LOWER(name), country_id, id FROM raw_assets")
            existing_assets = {(row[0], str(row[1])): str(row[2]) for row in cursor.fetchall()}

            success_count = 0
            failed_items = []

            for _, row in df.iterrows():
                name = str(row.get('Name', '')).strip()
                if not name: continue

                desc = str(row.get('Description', '')).strip()
                type_str = str(row.get('Asset Type', '')).strip().lower()
                country_str = str(row.get('Country', '')).strip().lower()
                service_str = str(row.get('Service Lane', '')).strip().lower()
                cat_str = str(row.get('Category', '')).strip().lower()

                internet_val = str(row.get('Facing Internet', '')).strip().lower()
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

                # Check if it already exists (UPSERT logic)
                existing_id = existing_assets.get((name.lower(), str(country_id)))

                try:
                    if existing_id:
                        cursor.execute("""
                            UPDATE raw_assets SET description=%s, business_critical=%s, 
                            confidentiality_rating=%s, integrity_rating=%s, availability_rating=%s, 
                            service_forecast_id=%s, category_id=%s, asset_type_id=%s, facing_internet=%s
                            WHERE id=%s
                        """, (desc, business_critical, c_val, i_val, a_val, service_id, cat_id, type_id,
                              facing_internet, existing_id))
                    else:
                        new_id = str(uuid.uuid4())
                        cursor.execute("""
                            INSERT INTO raw_assets (
                                id, name, description, business_critical, 
                                confidentiality_rating, integrity_rating, availability_rating, 
                                country_id, service_forecast_id, category_id, asset_type_id, facing_internet
                            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        """, (new_id, name, desc, business_critical, c_val, i_val, a_val, country_id, service_id,
                              cat_id, type_id, facing_internet))

                    success_count += 1
                except Exception:
                    cursor.connection.rollback()
                    failed_items.append(f"{name} (DB Error)")

            cursor.connection.commit()

            if failed_items:
                log_audit_event(
                    user_id=str(current_user["id"]), username=current_user["name"],
                    action="IMPORT_WARNINGS", resource_type="ASSETS",
                    details=f"Failed to import {len(failed_items)} rows: {', '.join(failed_items[:10])}{'...' if len(failed_items) > 10 else ''}"
                )

            return success_count, failed_items

        except Exception as e:
            return 0, [f"File formatting error: {str(e)}"]


@router.post("/raw/import")
async def import_assets(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(),
                        current_user: dict = Depends(require_admin)):
    contents = await file.read()

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
@router.post("/promote")
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
        promoted += 1

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": f"Successfully promoted {promoted} assets to the Active Pool."}


# --- ACTIVE ASSET POOL ---
@router.get("/")
def get_active_asset_pool(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user['role'] == 'pentester':
        raise HTTPException(status_code=403, detail="Pentesters cannot view the unassigned asset inventory.")
    cursor.execute('''
        SELECT a.id, a.name, c.name as country, s.name as service_forecast, cat.name as category_name, at.name as asset_type_name, a.is_assigned
        FROM assets a
        LEFT JOIN countries c ON a.country_id = c.id
        LEFT JOIN services_lanes s ON a.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON a.category_id = cat.id
        LEFT JOIN asset_types at ON a.asset_type_id = at.id
        ORDER BY a.name ASC
    ''')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.delete("/{asset_id}")
def remove_from_active_pool(asset_id: str, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Asset returned to raw data pool."}