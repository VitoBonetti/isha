from fastapi import APIRouter, Depends, status, BackgroundTasks
from database import get_db_cursor
from routers.auth import get_current_user, require_admin, require_admin_or_pentester
from schema import ReconcileAssetPayload, BulkReconcileAssetPayload
from system_services import kiss24_app_service

router = APIRouter(prefix="/api/kiss24", tags=["Kiss24"])

@router.post("/sync-org-ids", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_org_ids(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.sync_kiss24_org_ids(cursor, current_user)


@router.post("/sync-asset-ids", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_asset_ids(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.sync_kiss24_asset_ids(cursor, current_user)


@router.post("/sync-update-kiss24-snowid", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_update_kiss24_snowid(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.sync_update_kiss24_snowid(cursor, current_user)


@router.post("/sync-vuln-types", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_vulnerability_types(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.sync_kiss24_vulnerability_types(cursor, current_user)


@router.post("/sync-user-kiss24-uuid", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_user_kiss24_uuid(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.sync_user_kiss24_uuid(cursor, current_user)


@router.post("/{test_id}/create-test", status_code=status.HTTP_200_OK)
def create_kiss24_test(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.create_kiss24_test(cursor, test_id, current_user)


@router.get("/{test_id}/live-status", status_code=status.HTTP_200_OK)
def get_kiss24_live_status(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.get_kiss24_live_status(cursor, test_id, current_user)


@router.get("/{test_id}/vulnerabilities", status_code=status.HTTP_200_OK)
def get_kiss24_vulnerabilities(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.get_kiss24_vulnerabilities(cursor, test_id, current_user)


@router.get("/vuln-types", status_code=status.HTTP_200_OK, summary="[Service Endpoint]")
def get_kiss24_vuln_types_for_dropdown(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.get_kiss24_vuln_types_for_dropdown(cursor)


@router.post("/{test_id}/vulnerabilities/publish", status_code=status.HTTP_200_OK)
def publish_vulnerability(test_id: str, payload: dict, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.publish_vulnerability(cursor, test_id, payload, current_user)


@router.get("/validating-vulns", summary="Get Cached Validating Vulns (Instant)")
def get_validating_vulns(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.get_validating_vulns(cursor)


@router.post("/validating-vulns/sync", summary="Reconcile & Sync with KISS24")
def sync_validating_vulns(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.sync_validating_vulns(cursor, current_user)


@router.put("/validating-vulns/{uuid}", summary="Update Local Vuln Info")
def update_validating_vuln(uuid: str, payload: dict, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.update_validating_vuln(cursor, uuid, payload, current_user)


@router.post("/validating-vulns/{uuid}/analyze")
def start_ai_analysis(uuid: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin_or_pentester), cursor=Depends(get_db_cursor)):
    user_api_key = kiss24_app_service.get_user_kiss24_key(cursor, str(current_user["id"]))
    background_tasks.add_task(kiss24_app_service.trigger_luigi_verification_pipeline, uuid, user_api_key)
    return {"message": "Luigi pipeline started"}


@router.get("/reconciliation-candidates", summary="[Admin] Get Unmapped Assets")
def get_reconciliation_candidates(limit: int = 0, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.get_reconciliation_candidates(cursor, limit)


@router.post("/reconcile-asset", summary="[Admin] Manually Link Mario Asset to KISS24")
def reconcile_asset(payload: ReconcileAssetPayload, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.reconcile_asset(cursor, payload, current_user)


@router.post("/reconcile-asset/bulk", summary="[Admin] Bulk Link Mario Assets to KISS24")
def bulk_reconcile_assets(payload: BulkReconcileAssetPayload, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return kiss24_app_service.bulk_reconcile_assets(cursor, payload, current_user)