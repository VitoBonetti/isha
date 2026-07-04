from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Query
from typing import Optional, List
from pydantic import BaseModel, UUID4
import pandas as pd
import io
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin
from models import RawAssetCreate, AssetBase
from websockets_manager import manager

router = APIRouter(prefix="/api/assets", tags=["Assets"])


class PromoteAssetRequest(BaseModel):
    raw_asset_ids: List[UUID4]


# --- 1. RAW ASSETS (The Intake Source) ---

@router.get("/raw")
def get_raw_assets(
        page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=500),
        search: Optional[str] = None, country_id: Optional[str] = None,
        service_id: Optional[str] = None,
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

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # Check if they are already promoted
    query = f"""
        SELECT r.id, r.name, c.name as country_name, s.name as service_name, 
               CASE WHEN a.id IS NOT NULL THEN true ELSE false END as is_promoted
        FROM raw_assets r
        LEFT JOIN countries c ON r.country_id = c.id
        LEFT JOIN service_lanes s ON r.service_forecast_id = s.id
        LEFT JOIN assets a ON r.id = a.raw_asset_id
        {where_str}
        ORDER BY r.name DESC
        LIMIT %s OFFSET %s
    """

    cursor.execute(query, tuple(params + [limit, offset]))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/raw")
def create_manual_raw_asset(asset: RawAssetCreate, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # FIX: Explicitly cast UUID4 objects to strings for psycopg2
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


def process_excel_import(contents: bytes):
    # Lean importer: Just reads Name, Country Code, and Service Lane name to map to IDs.
    with db_cursor_context() as cursor:
        if not cursor: return
        try:
            df = pd.read_excel(io.BytesIO(contents))
            df = df.fillna('')
            for _, row in df.iterrows():
                name = str(row.get('Name', '')).strip()
                if not name: continue

                # We would map country codes and service names to UUIDs here in a full implementation
                # For now, we insert safely
                cursor.execute("""
                    INSERT INTO raw_assets (name, description) VALUES (%s, %s)
                """, (name, str(row.get('Description', ''))))
        except Exception as e:
            print(f"Import Failed: {e}")


@router.post("/raw/import")
async def import_assets(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(),
                        current_user: dict = Depends(require_admin)):
    contents = await file.read()
    background_tasks.add_task(process_excel_import, contents)
    return {"message": "Standard format import started in the background."}


# --- 2. THE PROMOTION ENGINE ---

@router.post("/promote")
def promote_raw_assets_to_pool(req: PromoteAssetRequest, background_tasks: BackgroundTasks,
                               current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """Moves selected Raw Assets into the active Asset Pool for testing."""
    promoted = 0
    for raw_id in req.raw_asset_ids:
        # Check if it already exists in the pool
        cursor.execute("SELECT id FROM assets WHERE raw_asset_id = %s", (str(raw_id),))
        if cursor.fetchone(): continue

        # Fetch the raw data
        cursor.execute("SELECT name, country_id, service_forecast_id FROM raw_assets WHERE id = %s", (str(raw_id),))
        raw_data = cursor.fetchone()
        if not raw_data: continue

        # Insert into the active pool
        cursor.execute("""
            INSERT INTO assets (raw_asset_id, name, country_id, service_forecast_id)
            VALUES (%s, %s, %s, %s)
        """, (str(raw_id), raw_data[0], raw_data[1], raw_data[2]))
        promoted += 1

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": f"Successfully promoted {promoted} assets to the Active Pool."}


# --- 3. ACTIVE ASSET POOL ---

@router.get("/")
def get_active_asset_pool(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user['role'] == 'pentester':
        raise HTTPException(status_code=403, detail="Pentesters cannot view the unassigned asset inventory.")

    cursor.execute('''
        SELECT a.id, a.name, c.name as country, s.name as service_forecast, a.is_assigned
        FROM assets a
        LEFT JOIN countries c ON a.country_id = c.id
        LEFT JOIN service_lanes s ON a.service_forecast_id = s.id
        ORDER BY a.name ASC
    ''')

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.delete("/{asset_id}")
def remove_from_active_pool(asset_id: str, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """Removes an asset from the Active Pool (It remains in Raw Data)."""
    cursor.execute("DELETE FROM assets WHERE id = %s", (asset_id,))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Asset returned to raw data pool."}