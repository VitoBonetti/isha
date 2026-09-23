from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import require_admin, require_admin_or_read_only
from system_services import log_service
from schema import LogSearchRequest

router = APIRouter(prefix="/api/system/logs", tags=["Logs"])


@router.get("/", summary="[Admin Only]")
def get_recent_logs(current_user: dict = Depends(require_admin_or_read_only)):
    """
    Admin Only endpoint to Queries BigQuery for the 100 most recent logs for the UI terminal.
    """
    return log_service.get_recent_logs()


@router.get("/filters", summary="[Admin Only] Get dynamic BigQuery log filters")
def get_audit_log_filters(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Returns unique resources, actions, and mapped users for the search dropdowns."""
    return log_service.get_log_filters(db)


@router.post("/search", summary="[Admin Only] Advanced Paginated Log Search")
def search_audit_logs(req: LogSearchRequest, current_user: dict = Depends(require_admin)):
    """Queries BigQuery using dynamic filters, timeframes, and pagination."""
    return log_service.search_audit_logs(req, current_user)


@router.get("/download/csv", summary="[Admin Only]")
def download_logs_csv(current_user: dict = Depends(require_admin)):
    """
    Admin Only endpoint to Generates a dynamic CSV file of ALL logs from BigQuery.
    """
    return log_service.download_logs_csv(current_user)


@router.post("/search/download/csv", summary="[Admin Only] Download filtered logs as CSV")
def download_filtered_logs_csv(req: LogSearchRequest, current_user: dict = Depends(require_admin)):
    """Downloads all logs matching the advanced search criteria as a CSV."""
    return log_service.download_search_logs_csv(req, current_user)


@router.delete("/clear", summary="[Admin Only]")
def clear_all_logs(current_user: dict = Depends(require_admin)):
    """
    Admin Only endpoint to Deletes all data from the BigQuery table.
    """
    return log_service.clear_all_logs(current_user)