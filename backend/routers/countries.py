from fastapi import APIRouter, Depends
from typing import Optional
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_admin_or_read_only
from schema import CountryBase
from system_services import country_service

router = APIRouter(prefix="/api/countries", tags=["Countries"])


@router.get(
    "/",
    summary="Get All Countries"
)
def get_countries(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve all configured countries and regions from the database.

    Returns a list of geographical markets utilized in the platform for grouping and categorizing
    assets, compliance scope, and test distributions.
    """
    return country_service.get_countries(db, current_user)


@router.post(
    "/",
    summary="[Admin Only] Create Country"
)
def create_country(c: CountryBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Add a new country or region to the platform configuration.

    Administrators can define a new geographic market to which future tests and assets can be assigned.
    """
    return country_service.create_country(db, c, current_user)


@router.put(
    "/{country_id}",
    summary="[Admin Only] Update Country"
)
def update_country(country_id: str, c: CountryBase, current_user: dict = Depends(require_admin),
                   db: Session = Depends(get_db)):
    """
    Modify an existing country's details.

    Updates properties like the country name or its integration mappings (e.g., Kiss24 Country UUID).
    """
    return country_service.update_country(db, country_id, c, current_user)


@router.delete(
    "/{country_id}",
    summary="[Admin Only] Delete Country"
)
def delete_country(country_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Remove a country from the platform.

    Permanently deletes a geographic region. This action may fail if there are active raw assets
    or tests currently assigned to this country ID.
    """
    return country_service.delete_country(db, country_id, current_user)


@router.get(
    "/analytics",
    summary="[Admin Only] Get Country Analytics"
)
def get_country_analytics(year: Optional[int] = None, current_user: dict = Depends(require_admin_or_read_only),
                          db: Session = Depends(get_db)):
    """
    Retrieve security test distribution metrics grouped by Country.

    Provides high-level aggregated data for regional reporting. If a year is omitted,
    the engine will compile analytics for the current operational year.
    """
    return country_service.get_country_analytics(db, year)


@router.get(
    "/available-years",
    summary="[Admin/ReadOnly] Get Available Reporting Years"
)
def get_available_years(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Retrieve all active years present in the analytics database.

    Fetches a distinct list of operational years that have recorded test or asset data,
    used primarily to populate frontend dropdown filters.
    """
    return country_service.get_available_years(db)


@router.get(
    "/dashboard",
    summary="[Admin/ReadOnly] Get Global Dashboard Analytics"
)
def get_dashboard_analytics(year: Optional[int] = None, country_id: Optional[str] = None,
                            region_id: Optional[str] = None, service_lane_id: Optional[str] = None,
                            current_user: dict = Depends(require_admin_or_read_only),
                            db: Session = Depends(get_db)):
    """
    Fetch comprehensive dashboard metrics with dynamic slice-and-dice parameters.

    Powers the primary executive dashboard view. Data can be dynamically aggregated and filtered
    by specific year, individual country, broader geographical region, or specific service lane constraints.
    """
    return country_service.get_dashboard_analytics(db, year, country_id, region_id, service_lane_id)