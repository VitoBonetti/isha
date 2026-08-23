from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, UUID4
from database import get_db_cursor
from schema import LocationBase
from routers.auth import get_current_user, require_admin
import uuid
from audit_logger import log_audit_event

router = APIRouter(prefix="/api/locations", tags=["Locations"])


@router.get("/")
def get_locations(current_user: dict = Depends(get_current_user), cursor = Depends(get_db_cursor)):
    """
    Endpoint to Get Locations
    """
    cursor.execute("SELECT id, name, is_active FROM locations ORDER BY name")
    return [{"id": r[0], "name": r[1], "is_active": r[2]} for r in cursor.fetchall()]


@router.post("/", summary="[Admin Only]")
def create_location(loc: LocationBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Create Location
    """
    new_location_id = str(uuid.uuid4())
    try:
        cursor.execute("INSERT INTO locations (id, name, is_active) VALUES (%s, %s, %s)", (new_location_id, loc.name, loc.is_active))
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="LOCATION_CREATED",
            resource_type="LOCATIONS",
            resource_id=str(new_location_id),
            details=f"Location {loc.name} with ID: {new_location_id} was created."
        )

        return {"id": new_location_id, "message": "Location created."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=400, detail=f"Location name already exists. {e}")


@router.put("/{loc_id}", summary="[Admin Only]")
def update_location(loc_id: str, loc: LocationBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Update Location
    """
    cursor.execute("UPDATE locations SET name=%s, is_active=%s WHERE id=%s", (loc.name, loc.is_active, loc_id))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="LOCATION_UPDATED",
        resource_type="LOCATIONS",
        resource_id=str(loc_id),
        details=f"Location with ID: {loc_id} was updated."
    )

    return {"message": "Location updated."}


@router.delete("/{loc_id}", summary="[Admin Only]")
def delete_location(loc_id: str, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Delete Location
    """
    cursor.execute("DELETE FROM locations WHERE id = %s", (loc_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="LOCATION_DELETED",
        resource_type="LOCATIONS",
        resource_id=str(loc_id),
        details=f"Location with ID: {loc_id} was deleted."
    )

    return {"message": "Location deleted."}