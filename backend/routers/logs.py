from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from database import get_db
from routers.auth import require_admin, require_admin_or_read_only
from system_services import log_service
from schema import LogSearchRequest

router = APIRouter(prefix="/api/system/logs", tags=["Logs"])


@router.get(
    "/",
    summary="[Admin/ReadOnly] Get Recent Logs"
)
def get_recent_logs(current_user: dict = Depends(require_admin_or_read_only)):
    """
    Retrieve the most recent system audit events.

    Queries the external BigQuery data warehouse to fetch the 100 most recent
    system logs, used to populate the live terminal view in the frontend UI.
    """
    return log_service.get_recent_logs()


@router.get(
    "/filters",
    summary="[Admin Only] Get Log Search Filters"
)
def get_audit_log_filters(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Retrieve dynamically generated filter options for the search interface.

    Queries BigQuery to extract unique resource types, action categories,
    and mapped users to populate the dropdown menus in the advanced log search UI.
    """
    return log_service.get_log_filters(db)


@router.post(
    "/search",
    summary="[Admin Only] Advanced Paginated Log Search"
)
def search_audit_logs(req: LogSearchRequest, current_user: dict = Depends(require_admin)):
    """
    Execute a complex search query against the audit log table.

    Translates the frontend search payload into a dynamic BigQuery SQL statement,
    supporting pagination, timeframe boundaries, and specific filtering by user or action.
    """
    return log_service.search_audit_logs(req, current_user)


@router.get(
    "/download/csv",
    summary="[Admin Only] Download All Logs (CSV)"
)
def download_logs_csv(current_user: dict = Depends(require_admin)):
    """
    Generate and download a complete extract of the audit trail.

    Pulls every single log entry currently stored in BigQuery and streams it
    back to the client as a raw CSV file for external compliance auditing.
    """
    return log_service.download_logs_csv(current_user)


@router.post(
    "/search/download/csv",
    summary="[Admin Only] Download Filtered Logs (CSV)"
)
def download_filtered_logs_csv(req: LogSearchRequest, current_user: dict = Depends(require_admin)):
    """
    Export a targeted subset of audit logs.

    Applies the exact filters from the advanced search interface and exports
    only the matching log entries to a downloadable CSV format.
    """
    return log_service.download_search_logs_csv(req, current_user)


@router.delete(
    "/clear",
    summary="[Admin Only] Clear All Audit Logs"
)
def clear_all_logs(current_user: dict = Depends(require_admin)):
    """
    **DANGER ZONE:** Permanently erase the entire system audit trail.

    Issues a direct truncation command to the BigQuery dataset, deleting all
    historical log data. This action cannot be undone.
    """
    return log_service.clear_all_logs(current_user)