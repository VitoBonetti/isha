# routers/regions.py
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
from system_services import region_service
from schema import RegionBase

router = APIRouter(prefix="/api/regions", tags=["Regions"])


@router.get("/")
def get_regions(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Endpoint to get all regions
    """
    return region_service.get_regions(cursor, current_user)


@router.post("/", summary="[Admin Only]")
def create_region(r: RegionBase, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to create a new region
    """
    return region_service.create_region(cursor, r, current_user)


@router.put("/{region_id}", summary="[Admin Only]")
def update_region(region_id: str, r: RegionBase, current_user: dict = Depends(require_admin),
                  cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to update a region
    """
    return region_service.update_region(cursor, region_id, r, current_user)


@router.delete("/{region_id}", summary="[Admin Only]")
def delete_region(region_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to delete a region
    """
    return region_service.delete_region(cursor, region_id, current_user)