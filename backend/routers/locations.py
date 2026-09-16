from fastapi import APIRouter, Depends
from database import get_db
from sqlalchemy.orm import Session
from schema import LocationBase
from routers.auth import get_current_user, require_admin
from system_services import locations_service

router = APIRouter(prefix="/api/locations", tags=["Locations"])


@router.get("/")
def get_locations(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to Get Locations
    """
    return locations_service.get_locations(db, current_user)


@router.post("/", summary="[Admin Only]")
def create_location(loc: LocationBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Create Location
    """
    return locations_service.create_location(db, loc, current_user)


@router.put("/{loc_id}", summary="[Admin Only]")
def update_location(loc_id: str, loc: LocationBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Update Location
    """
    return locations_service.update_location(db, loc_id, loc, current_user)


@router.delete("/{loc_id}", summary="[Admin Only]")
def delete_location(loc_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Delete Location
    """
    return locations_service.delete_location(db, loc_id, current_user)