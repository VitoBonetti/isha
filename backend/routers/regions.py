from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, UUID4
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
import uuid

router = APIRouter(prefix="/api/regions", tags=["Regions"])


class RegionBase(BaseModel):
    name: str
    is_active: bool = True


@router.get("/")
def get_regions(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') == 'pentester':
        raise HTTPException(status_code=403, detail="Pentesters cannot access region data.")

    cursor.execute("SELECT id, name, is_active FROM regions ORDER BY name")
    return [{"id": r[0], "name": r[1], "is_active": r[2]} for r in cursor.fetchall()]


@router.post("/")
def create_region(r: RegionBase, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):

    new_region_id = str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO regions (id, name, is_active) VALUES (%s, %s, %s)",
            (new_region_id, r.name, r.is_active)
        )
        cursor.connection.commit()
        return {"id": new_region_id, "message": "Region created."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=400, detail="Region name already exists.")


@router.put("/{region_id}")
def update_region(region_id: str, r: RegionBase, current_user: dict = Depends(require_admin),
                  cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE regions SET name=%s, is_active=%s WHERE id=%s", (r.name, r.is_active, region_id))
    cursor.connection.commit()
    return {"message": "Region updated."}


@router.delete("/{region_id}")
def delete_region(region_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM regions WHERE id = %s", (region_id,))
    cursor.connection.commit()
    return {"message": "Region deleted."}