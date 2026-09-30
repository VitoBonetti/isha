from fastapi import APIRouter, Depends
from database import get_db
from sqlalchemy.orm import Session
from schema import LocationBase
from routers.auth import get_current_user, require_admin
from system_services import locations_service

router = APIRouter(prefix="/api/locations", tags=["Locations"])


@router.get("/", summary="Get All Facilities/Locations")
def get_locations(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve all operational facility locations.

    Fetches the active dictionary of physical office locations, data centers, and facilities
    used for categorizing users and hardware assets.
    """
    return locations_service.get_locations(db, current_user)


@router.post("/", summary="[Admin Only] Create Location")
def create_location(loc: LocationBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Define a new facility or office location for the platform.
    """
    return locations_service.create_location(db, loc, current_user)


@router.put("/{loc_id}", summary="[Admin Only] Update Location")
def update_location(loc_id: str, loc: LocationBase, current_user: dict = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """
    Modify the address or active status of an existing facility location.
    """
    return locations_service.update_location(db, loc_id, loc, current_user)


@router.delete("/{loc_id}", summary="[Admin Only] Delete Location")
def delete_location(loc_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Permanently remove a location from the dictionary.

    This action will fail if the location is currently assigned to active users or assets.
    """
    return locations_service.delete_location(db, loc_id, current_user)