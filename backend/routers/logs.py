from fastapi import APIRouter, Depends
from routers.auth import require_admin, require_admin_or_read_only
from system_services import log_service

router = APIRouter(prefix="/api/system/logs", tags=["Logs"])


@router.get("/", summary="[Admin Only]")
def get_recent_logs(current_user: dict = Depends(require_admin_or_read_only)):
    """
    Admin Only endpoint to Queries BigQuery for the 100 most recent logs for the UI terminal.
    """
    return log_service.get_recent_logs()


@router.get("/download/csv", summary="[Admin Only]")
def download_logs_csv(current_user: dict = Depends(require_admin)):
    """
    Admin Only endpoint to Generates a dynamic CSV file of ALL logs from BigQuery.
    """
    return log_service.download_logs_csv(current_user)


@router.delete("/clear", summary="[Admin Only]")
def clear_all_logs(current_user: dict = Depends(require_admin)):
    """
    Admin Only endpoint to Deletes all data from the BigQuery table.
    """
    return log_service.clear_all_logs(current_user)