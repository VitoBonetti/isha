from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Query
from typing import Optional, List
from pydantic import BaseModel, UUID4
import pandas as pd
import io
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin
from schema import RawAssetCreate, AssetBase
from websockets_manager import manager

router = APIRouter(prefix="/api/assets", tags=["Assets"])

class PromoteAssetRequest(BaseModel):
    raw_asset_ids: List[UUID4]


# --- RAW ASSETS (The Intake Source) ---
@router.get("/raw")
def get_raw_assets(
        page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=500),
        search: Optional[str] = None, country_id: Optional[str] = None,
        service_id: Optional[str] = None, category_id: Optional[str] = None,
        status: Optional[str] = None, sort_by: Optional[str] = "name", sort_dir: Optional[str] = "asc",
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
    if status == 'raw':
        where_clauses.append("a.id IS NULL")
    elif status == 'pool':
        where_clauses.append("a.id IS NOT NULL")

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Map frontend sort keys to database columns securely
    sort_map = {
        "name": "r.name",
        "country": "c.name",
        "service": "s.name",
        "category": "cat.name",
        "status": "is_promoted"
    }
    order_col = sort_map.get(sort_by, "r.name")
    order_dir = "DESC" if sort_dir.lower() == "desc" else "ASC"

    query = f"""
        SELECT r.id, r.name, c.name as country_name, s.name as service_name, cat.name as category_name,
               CASE WHEN a.id IS NOT NULL THEN true ELSE false END as is_promoted
        FROM raw_assets r
        LEFT JOIN countries c ON r.country_id = c.id
        LEFT JOIN service_lanes s ON r.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON r.category_id = cat.id
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

    cursor.execute("""
        INSERT INTO raw_assets (
            name, description, business_critical, 
            confidentiality_rating, integrity_rating, availability_rating, 
            country_id, service_forecast_id, category_id
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) RETURNING id
    """, (
        asset.name, asset.description, asset.business_critical,
        asset.confidentiality_rating, asset.integrity_rating, asset.availability_rating,
        c_id, s_id, cat_id
    ))

    new_id = cursor.fetchone()[0]
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Raw Asset created", "id": new_id}


@router.get("/raw/{raw_id}")
def get_single_raw_asset(raw_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("""
        SELECT r.id, r.name, r.description, r.business_critical, r.confidentiality_rating, 
               r.integrity_rating, r.availability_rating, r.country_id, r.service_forecast_id, r.category_id,
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

    cursor.execute("""
        UPDATE raw_assets 
        SET name=%s, description=%s, business_critical=%s, 
            confidentiality_rating=%s, integrity_rating=%s, availability_rating=%s, 
            country_id=%s, service_forecast_id=%s, category_id=%s
        WHERE id=%s
    """, (
        asset.name, asset.description, asset.business_critical,
        asset.confidentiality_rating, asset.integrity_rating, asset.availability_rating,
        c_id, s_id, cat_id, raw_id
    ))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Raw Asset updated"}


@router.delete("/raw/{raw_id}")
def delete_raw_asset(raw_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Deleting the raw asset automatically removes it from the active pool via SQL CASCADE
    cursor.execute("DELETE FROM raw_assets WHERE id = %s", (raw_id,))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Asset permanently deleted"}


def process_excel_import(contents: bytes, filename: str):
    with db_cursor_context() as cursor:
        if not cursor: return
        try:
            # Smart fallback: Parse as CSV if the file extension matches
            if filename.lower().endswith('.csv'):
                df = pd.read_csv(io.BytesIO(contents))
            else:
                df = pd.read_excel(io.BytesIO(contents))

            df = df.fillna('')
            for _, row in df.iterrows():
                name = str(row.get('Name', '')).strip()
                if not name: continue

                cursor.execute(
                    "INSERT INTO raw_assets (name, description) VALUES (%s, %s)",
                    (name, str(row.get('Description', '')))
                )
        except Exception as e:
            print(f"Import Failed: {e}")


@router.post("/raw/import")
async def import_assets(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(),
                        current_user: dict = Depends(require_admin)):
    contents = await file.read()
    # Pass the filename so Pandas knows how to parse it
    background_tasks.add_task(process_excel_import, contents, file.filename)
    return {"message": "Standard format import started in the background."}


# --- THE PROMOTION ENGINE ---
@router.post("/promote")
def promote_raw_assets_to_pool(req: PromoteAssetRequest, background_tasks: BackgroundTasks,
                               current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    promoted = 0
    for raw_id in req.raw_asset_ids:
        cursor.execute("SELECT id FROM assets WHERE raw_asset_id = %s", (str(raw_id),))
        if cursor.fetchone(): continue

        cursor.execute("SELECT name, country_id, service_forecast_id, category_id FROM raw_assets WHERE id = %s", (str(raw_id),))
        raw_data = cursor.fetchone()
        if not raw_data: continue

        cursor.execute("""
            INSERT INTO assets (raw_asset_id, name, country_id, service_forecast_id, category_id)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(raw_id), raw_data[0], raw_data[1], raw_data[2], raw_data[3]))
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
        SELECT a.id, a.name, c.name as country, s.name as service_forecast, cat.name as category_name, a.is_assigned
        FROM assets a
        LEFT JOIN countries c ON a.country_id = c.id
        LEFT JOIN service_lanes s ON a.service_forecast_id = s.id
        LEFT JOIN service_categories cat ON a.category_id = cat.id
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