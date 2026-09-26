from fastapi import APIRouter, Depends, BackgroundTasks
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