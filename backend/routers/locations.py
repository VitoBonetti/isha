from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, UUID4
from database import get_db_cursor
from schema import LocationBase
from routers.auth import get_current_user, require_admin
import uuid

router = APIRouter(prefix="/api/locations", tags=["Locations"])


@router.get("/")
def get_locations(current_user: dict = Depends(get_current_user), cursor = Depends(get_db_cursor)):
    cursor.execute("SELECT id, name, is_active FROM locations ORDER BY name")
    return [{"id": r[0], "name": r[1], "is_active": r[2]} for r in cursor.fetchall()]


@router.post("/")
def create_location(loc: LocationBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    new_location_id = str(uuid.uuid4())
    try:
        cursor.execute("INSERT INTO locations (id, name, is_active) VALUES (%s, %s, %s)", (new_location_id, loc.name, loc.is_active))
        cursor.connection.commit()
        return {"id": new_location_id, "message": "Location created."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=400, detail=f"Location name already exists. {e}")


@router.put("/{loc_id}")
def update_location(loc_id: str, loc: LocationBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    cursor.execute("UPDATE locations SET name=%s, is_active=%s WHERE id=%s", (loc.name, loc.is_active, loc_id))
    cursor.connection.commit()
    return {"message": "Location updated."}


@router.delete("/{loc_id}")
def delete_location(loc_id: str, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    cursor.execute("DELETE FROM locations WHERE id = %s", (loc_id,))
    cursor.connection.commit()
    return {"message": "Location deleted."}
