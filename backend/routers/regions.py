from fastapi import APIRouter, Depends
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin
from system_services import region_service
from schema import RegionBase

router = APIRouter(prefix="/api/regions", tags=["Regions"])


@router.get("/")
def get_regions(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to get all regions
    """
    return region_service.get_regions(db, current_user)


@router.post("/", summary="[Admin Only]")
def create_region(r: RegionBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to create a new region
    """
    return region_service.create_region(db, r, current_user)


@router.put("/{region_id}", summary="[Admin Only]")
def update_region(region_id: str, r: RegionBase, current_user: dict = Depends(require_admin),
                  db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to update a region
    """
    return region_service.update_region(db, region_id, r, current_user)


@router.delete("/{region_id}", summary="[Admin Only]")
def delete_region(region_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to delete a region
    """
    return region_service.delete_region(db, region_id, current_user)