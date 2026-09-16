import uuid
from fastapi import HTTPException
from audit_logger import log_audit_event


def get_regions(cursor, current_user: dict):
    role_allowed = ['admin', 'read_only', 'pentester']

    if current_user.get('role') not in role_allowed:
        raise HTTPException(status_code=403, detail=f"{current_user.get('role')} cannot access region data.")

    cursor.execute("SELECT id, name, is_active FROM regions ORDER BY name")
    return [{"id": r[0], "name": r[1], "is_active": r[2]} for r in cursor.fetchall()]


def create_region(cursor, r, current_user: dict):
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


def update_region(cursor, region_id: str, r, current_user: dict):
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


def delete_region(cursor, region_id: str, current_user: dict):
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