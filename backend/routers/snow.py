from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from database import get_db
from routers.auth import require_admin
from system_services import snow_service


router = APIRouter(prefix="/api/snow", tags=["ServiceNow Tools"])

@router.post("/sync-ritms")
def trigger_ritm_sync(
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_admin)
):
    """
    Triggers the background process to fetch, parse, and upsert the latest RITM sheet
    from the GCS bucket, then archives the file.
    """
    background_tasks.add_task(
        snow_service.process_ritm_sync_background,
        str(current_user["id"]),
        current_user.get("role", "admin")
    )

    return {"message": "RITM Sync background task has been successfully triggered."}


@router.get("/ritm-last-sync")
def get_ritm_last_sync(current_user: dict = Depends(require_admin)):
    """
    Fetches the last successful RITM sync timestamp directly from BigQuery audit logs.
    """
    return snow_service.get_last_ritm_sync_date()


@router.get("/ritms/current-year")
def get_ritms_endpoint(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search_id: Optional[str] = None,
    stage: Optional[str] = None,
    company: Optional[str] = None,
    name_app: Optional[str] = None,
    created_exact: Optional[date] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
    estimated_exact: Optional[date] = None,
    estimated_from: Optional[date] = None,
    estimated_to: Optional[date] = None
):
    """
    Fetches filtered ServiceNow RITM requests.
    Base Rule: Includes records targeting the current year and excludes 'Request Cancelled'.
    """
    current_year = int(datetime.now(timezone.utc).year)

    return snow_service.get_filtered_ritms_current_year(
        db=db,
        page=page,
        limit=limit,
        search_id=search_id,
        stage=stage,
        company=company,
        name_app=name_app,
        created_exact=created_exact,
        created_from=created_from,
        created_to=created_to,
        estimated_exact=estimated_exact,
        estimated_from=estimated_from,
        estimated_to=estimated_to,
        current_year=current_year
    )


@router.get("/ritms/all-year")
def get_ritms_endpoint(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin),
    page: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=500),
    search_id: Optional[str] = None,
    stage: Optional[str] = None,
    company: Optional[str] = None,
    name_app: Optional[str] = None,
    created_exact: Optional[date] = None,
    created_from: Optional[date] = None,
    created_to: Optional[date] = None,
    estimated_exact: Optional[date] = None,
    estimated_from: Optional[date] = None,
    estimated_to: Optional[date] = None
):
    """
    Fetches filtered ServiceNow RITM requests.
    Base Rule:Excludes 'Request Cancelled'.
    """

    return snow_service.get_filtered_ritms_current_year(
        db=db,
        page=page,
        limit=limit,
        search_id=search_id,
        stage=stage,
        company=company,
        name_app=name_app,
        created_exact=created_exact,
        created_from=created_from,
        created_to=created_to,
        estimated_exact=estimated_exact,
        estimated_from=estimated_from,
        estimated_to=estimated_to,
        current_year=None
    )


@router.get("/match-tests")
def match_tests_endpoint(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Matches active current-year tests against ServiceNow RITM requests using OneTrust Asset IDs.
    Returns matched records, unmatched tests, and unmatched RITMs.
    """
    return snow_service.match_tests_with_ritms(db)