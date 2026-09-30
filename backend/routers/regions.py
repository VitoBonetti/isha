from fastapi import APIRouter, Depends
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin
from system_services import region_service
from schema import RegionBase

router = APIRouter(prefix="/api/regions", tags=["Regions"])


@router.get(
    "/",
    summary="Get All Regions"
)
def get_regions(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve all geographic regions.

    Fetches the configured list of global regions (e.g., NA, EMEA, APAC) used to
    categorize countries, assets, and operational scope.
    """
    return region_service.get_regions(db, current_user)


@router.post(
    "/",
    summary="[Admin Only] Create Region"
)
def create_region(r: RegionBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Add a new geographic region to the system dictionary.

    Administrators can define macro-regions to help group individual countries for
    reporting and dashboard aggregation.
    """
    return region_service.create_region(db, r, current_user)


@router.put(
    "/{region_id}",
    summary="[Admin Only] Update Region"
)
def update_region(region_id: str, r: RegionBase, current_user: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    """
    Modify an existing region's details.

    Updates the text properties or configuration of a specific geographical region.
    """
    return region_service.update_region(db, region_id, r, current_user)


@router.delete(
    "/{region_id}",
    summary="[Admin Only] Delete Region"
)
def delete_region(region_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Permanently delete a region.

    Removes a region from the platform. This action will fail if there are countries
    actively assigned to this region ID.
    """
    return region_service.delete_region(db, region_id, current_user)