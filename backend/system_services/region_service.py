from fastapi import HTTPException
from audit_logger import log_audit_event
from sqlalchemy.orm import Session
from models.territories import Region


def get_regions(db: Session, current_user: dict):
    role_allowed = ['admin', 'read_only', 'pentester']

    if current_user.get('role') not in role_allowed:
        raise HTTPException(status_code=403, detail=f"{current_user.get('role')} cannot access region data.")

    regions = db.query(Region).order_by(Region.name).all()
    return regions


def create_region(db: Session, r, current_user: dict):
    try:
        # Create a new ORM instance
        new_region = Region(name=r.name, is_active=r.is_active)

        # Add and commit it to the database
        db.add(new_region)
        db.commit()
        # Refreshes to get the auto-generated UUID
        db.refresh(new_region)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="REGION_CREATED",
            resource_type="REGIONS",
            resource_id=str(new_region.id),
            details=f"Region {new_region.name} with ID: {new_region.id} was created."
        )

        return {"id": str(new_region.id), "message": "Region created."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=400, detail="Region name already exists.")


def update_region(db: Session, region_id: str, r, current_user: dict):
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found.")

    # Update its attributes
    region.name = r.name
    region.is_active = r.is_active
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="REGION_UPDATED",
        resource_type="REGIONS",
        resource_id=str(region.id),
        details=f"Region with ID: {region.id} was updated."
    )

    return {"message": "Region updated."}


def delete_region(db: Session, region_id: str, current_user: dict):
    # Fetch the object
    region = db.query(Region).filter(Region.id == region_id).first()
    if not region:
        raise HTTPException(status_code=404, detail="Region not found.")

    # Delete it
    db.delete(region)
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="REGION_DELETED",
        resource_type="REGIONS",
        resource_id=str(region_id),
        details=f"Region with ID: {region_id} was deleted."
    )

    return {"message": "Region deleted."}