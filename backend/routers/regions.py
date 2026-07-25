from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, UUID4
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
import uuid
from audit_logger import log_audit_event

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


@router.post("/", summary="[Admin Only]")
def create_region(r: RegionBase, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):

    new_region_id = str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO regions (id, name, is_active) VALUES (%s, %s, %s)",
            (new_region_id, r.name, r.is_active)
        )
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="REGION_CREATED",
            resource_type="REGIONS",
            resource_id=str(new_region_id),
            details=f"Region {r.name} with ID: {new_region_id} was created."
        )

        return {"id": new_region_id, "message": "Region created."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=400, detail="Region name already exists.")


@router.put("/{region_id}", summary="[Admin Only]")
def update_region(region_id: str, r: RegionBase, current_user: dict = Depends(require_admin),
                  cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE regions SET name=%s, is_active=%s WHERE id=%s", (r.name, r.is_active, region_id))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="REGION_UPDATED",
        resource_type="REGIONS",
        resource_id=str(region_id),
        details=f"Region with ID: {region_id} was updated."
    )

    return {"message": "Region updated."}


@router.delete("/{region_id}", summary="[Admin Only]")
def delete_region(region_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM regions WHERE id = %s", (region_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="REGION_DELETED",
        resource_type="REGIONS",
        resource_id=str(region_id),
        details=f"Region with ID: {region_id} was deleted."
    )

    return {"message": "Region deleted."}
