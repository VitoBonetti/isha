import uuid
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from models.territories import Locations
from audit_logger import log_audit_event


def get_locations(db: Session, current_user: dict):
    if current_user.get('role') == 'mantainer':
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{current_user.get('role')} cannot access country data."
        )

    locations = db.query(Locations).order_by(Locations.name.asc()).all()
    return [{"id": str(r.id), "name": r.name, "is_active": r.is_active} for r in locations]


def create_location(db: Session, loc, current_user: dict):
    try:
        new_location = Locations(
            name=loc.name,
            is_active=loc.is_active
        )

        db.add(new_location)
        db.commit()
        db.refresh(new_location)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="LOCATION_CREATED",
            resource_type="LOCATIONS",
            resource_id=str(new_location.id),
            details=f"Location {loc.name} with ID: {new_location.id} was created."
        )

        return {"id": str(new_location.id), "message": "Location created."}
    except IntegrityError as e:
        db.rollback()
        raise HTTPException(status_code=400, detail=f"Location name already exists. {e}")


def update_location(db: Session, loc_id: str, loc, current_user: dict):
    location = db.query(Locations).filter(Locations.id == loc_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found.")

    location.name = loc.name
    location.is_active = loc.is_active
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="LOCATION_UPDATED",
        resource_type="LOCATIONS",
        resource_id=str(loc_id),
        details=f"Location with ID: {loc_id} was updated."
    )

    return {"message": "Location updated."}


def delete_location(db: Session, loc_id: str, current_user: dict):
    location = db.query(Locations).filter(Locations.id == loc_id).first()
    if not location:
        raise HTTPException(status_code=404, detail="Location not found.")

    db.delete(location)
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="LOCATION_DELETED",
        resource_type="LOCATIONS",
        resource_id=str(loc_id),
        details=f"Location with ID: {loc_id} was deleted."
    )

    return {"message": "Location deleted."}