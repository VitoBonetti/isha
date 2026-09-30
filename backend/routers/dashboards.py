from fastapi import APIRouter, Depends, BackgroundTasks
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import require_admin, require_admin_or_read_only
from system_services import dashboard_service

router = APIRouter()


@router.get(
    "/api/snitcher/",
    tags=["Snitcher Metrics"],
    summary="[Admin/ReadOnly] Get All Snitcher Metrics"
)
def get_all_metrics(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Retrieve all historically synced Snitcher metrics.

    Returns the complete dataset of weekly vulnerability tracking metrics,
    including team performance, user-specific ticket movements, and state transitions.
    """
    return dashboard_service.get_all_metrics(db)


@router.post(
    "/api/snitcher/sync",
    tags=["Snitcher Metrics"],
    summary="[Admin Only] Trigger Metrics Sync"
)
def trigger_snitcher_sync(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin)):
    """
    Launch the Snitcher Metrics data pipeline.

    Initiates an asynchronous background worker that connects to the external Vulnerability Manager,
    fetches the full asset and history ledgers, calculates KPI movements via a Pandas dataframe,
    and commits the aggregated metrics to the PostgreSQL database.
    """
    background_tasks.add_task(dashboard_service.run_snitcher_sync, current_user["id"], current_user["role"])
    return {"message": "Snitcher metrics sync started in the background. Check logs for completion."}


@router.delete(
    "/api/snitcher/wipe",
    tags=["Snitcher Metrics"],
    summary="[Admin Only] Wipe All Snitcher Metrics"
)
def wipe_snitcher_metrics(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    **DANGER ZONE:** Permanently delete all Snitcher metrics.

    Truncates the Snitcher tracking data from the database. This is primarily useful
    for clearing out testing data or resetting the dashboard to a blank state.
    """
    return dashboard_service.wipe_all_metrics(db)