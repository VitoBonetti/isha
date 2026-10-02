from fastapi import APIRouter, Depends, Query
from typing import Optional
from routers.auth_dash import get_dashboard_access
from system_services import global_dash_service

router = APIRouter(prefix="/api-global-dash", tags=["Global Dashboard"], include_in_schema=False)


@router.get("/vulnerabilities", summary="Get Filtered Watchtower Vulnerabilities")
def get_watchtower_vulnerabilities(
    opco: Optional[str] = Query("ALL"),
    severity: Optional[str] = Query("ALL"),
    state: Optional[str] = Query("ALL"),
    access_profile: dict = Depends(get_dashboard_access)
):
    return global_dash_service.get_dashboard_summary_and_items(
        access_profile=access_profile,
        opco_filter=opco,
        severity_filter=severity,
        state_filter=state
    )