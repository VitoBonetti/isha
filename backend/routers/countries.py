from fastapi import APIRouter, Depends
from typing import Optional
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_admin_or_read_only
from schema import CountryBase
from system_services import country_service

router = APIRouter(prefix="/api/countries", tags=["Countries"])


@router.get("/")
def get_countries(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return country_service.get_countries(db, current_user)


@router.post("/", summary="[Admin Only]")
def create_country(c: CountryBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Create Country
    """
    return country_service.create_country(db, c, current_user)


@router.put("/{country_id}", summary="[Admin Only]")
def update_country(country_id: str, c: CountryBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Update Country
    """
    return country_service.update_country(db, country_id, c, current_user)


@router.delete("/{country_id}", summary="[Admin Only]")
def delete_country(country_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Delete Country
    """
    return country_service.delete_country(db, country_id, current_user)


@router.get("/analytics", summary="[Admin Only]")
def get_country_analytics(year: Optional[int] = None, current_user: dict = Depends(require_admin_or_read_only),
                          db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Get Country Analytics
    """
    return country_service.get_country_analytics(db, year)


@router.get("/available-years", summary="[Admin Only]")
def get_available_years(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Get Available Years
    """
    return country_service.get_available_years(db)


@router.get("/dashboard", summary="[Admin Only]")
def get_dashboard_analytics(year: Optional[int] = None, country_id: Optional[str] = None,
                            region_id: Optional[str] = None, service_lane_id: Optional[str] = None,
                            current_user: dict = Depends(require_admin_or_read_only),
                            db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Get Dashboard Analytics
    """
    return country_service.get_dashboard_analytics(db, year, country_id, region_id, service_lane_id)