from datetime import date, datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session
from fastapi import APIRouter, Depends, BackgroundTasks, Query
from database import get_db
from routers.auth import require_admin
from system_services import snow_service
from schema import LinkRitmPayload

router = APIRouter(prefix="/api/snow", tags=["ServiceNow Tools"])

@router.post(
    "/sync-ritms",
    summary="[Admin Only] Trigger RITM Sync"
)
def trigger_ritm_sync(
        background_tasks: BackgroundTasks,
        current_user: dict = Depends(require_admin)
):
    """
    Launch a background synchronization to parse the latest RITM sheet.

    Triggers an asynchronous background process that fetches the latest ServiceNow RITM export
    from the connected GCS bucket, parses the spreadsheet, upserts the data into the internal database,
    and archives the processed file.
    """
    background_tasks.add_task(
        snow_service.process_ritm_sync_background,
        str(current_user["id"]),
        current_user.get("role", "admin")
    )

    return {"message": "RITM Sync background task has been successfully triggered."}


@router.get(
    "/ritm-last-sync",
    summary="[Admin Only] Get Last RITM Sync Time"
)
def get_ritm_last_sync(current_user: dict = Depends(require_admin)):
    """
    Fetch the timestamp of the last successful RITM sync.

    Queries the BigQuery audit logs directly to retrieve the exact timestamp of the
    most recent successfully completed RITM synchronization process.
    """
    return snow_service.get_last_ritm_sync_date()


@router.get(
    "/ritms/current-year",
    summary="[Admin Only] Get Current Year RITMs"
)
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
    estimated_to: Optional[date] = None,
    global_search: Optional[str] = None,
    sort_by: str = "created"
):
    """
    Fetch a paginated list of RITMs targeted for the current year.

    Retrieves filtered ServiceNow RITM requests from the database.
    **Base Rule:** This endpoint automatically restricts results to records whose estimated date
    or creation date falls within the current UTC year, and strictly excludes any requests with a 'Request Cancelled' stage.
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
        current_year=current_year,
        global_search=global_search,
        sort_by=sort_by
    )


@router.get(
    "/ritms/all-year",
    summary="[Admin Only] Get All RITMs (Unrestricted Year)"
)
def get_all_year_ritms_endpoint(
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
    estimated_to: Optional[date] = None,
    global_search: Optional[str] = None,
    sort_by: str = "created"
):
    """
    Fetch a paginated list of RITMs regardless of their target year.

    Retrieves filtered ServiceNow RITM requests from the database across all historical years.
    **Base Rule:** Unlike the current-year endpoint, this ignores the year restriction but
    still securely filters out 'Request Cancelled' stages.
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
        current_year=None,
        global_search=global_search,
        sort_by=sort_by
    )


@router.get(
    "/match-tests",
    summary="[Admin Only] Run RITM Reconciliation Engine"
)
def match_tests_endpoint(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Extract unmatched Tests and unmatched RITMs.

    Executes the reconciliation algorithm to identify orphaned active tests and orphaned RITMs.
    The matching logic relies primarily on querying OneTrust Asset IDs linked to both sets of records.
    """
    return snow_service.match_tests_with_ritms(db)


@router.post(
    "/link-test-ritm",
    summary="[Admin Only] Link Test to RITM"
)
def link_test_ritm_endpoint(
    payload: LinkRitmPayload,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Create a manual mapping between an orphaned Test and a RITM.

    Inserts a new relationship into the junction table connecting a specified Test ID
    to a ServiceNow RITM ID, and automatically updates the test's `ritm_matched` status flag.
    """
    return snow_service.link_test_to_ritm(db, payload.test_id, payload.ritm_id, current_user)


@router.post(
    "/unlink-test-ritm",
    summary="[Admin Only] Unlink Test from RITM"
)
def unlink_test_ritm_endpoint(
    payload: LinkRitmPayload,
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    Remove the manual mapping between a Test and a RITM.

    Deletes the specific relationship between a Test and a RITM from the junction table.
    If this leaves the test with zero linked RITMs, its `ritm_matched` flag is reverted to False.
    """
    return snow_service.unlink_test_from_ritm(db, payload.test_id, payload.ritm_id, current_user)


@router.post(
    "/unlink-all-test-ritm",
    summary="[Admin Only] Bulk Unlink All Tests & RITMs"
)
def bulk_unlink_ritms_and_tests(
    db: Session = Depends(get_db),
    current_user: dict = Depends(require_admin)
):
    """
    WARNING: Nuclear option to reset the entire reconciliation engine.

    **DANGER ZONE:** Removes all links across the entire system between Tests and RITMs
    and resets the `ritm_matched` flag to False for every test.
    This is highly destructive and primarily used for resetting the environment during integration testing.
    """
    return snow_service.unlink_all_tests_and_ritms(db, current_user)