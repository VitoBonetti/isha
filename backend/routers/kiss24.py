from fastapi import APIRouter, Depends, status, BackgroundTasks, Query
from database import get_db
from typing import Optional
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_admin_or_pentester
from schema import ReconcileAssetPayload, BulkReconcileAssetPayload, BulkAssetRequest
from system_services import kiss24_service

router = APIRouter(prefix="/api/kiss24", tags=["Kiss24"])

@router.post("/sync-org-ids", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_org_ids(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.sync_kiss24_org_ids(db, current_user)


@router.post("/sync-asset-ids", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_asset_ids(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.sync_kiss24_asset_ids(db, current_user)


@router.post("/sync-update-kiss24-snowid", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_update_kiss24_snowid(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.sync_update_kiss24_snowid(db, current_user)


@router.post("/sync-vuln-types", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_vulnerability_types(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.sync_kiss24_vulnerability_types(db, current_user)


@router.post("/sync-user-kiss24-uuid", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_user_kiss24_uuid(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.sync_user_kiss24_uuid(db, current_user)


@router.post("/{test_id}/create-test", status_code=status.HTTP_200_OK)
def create_kiss24_test(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.create_kiss24_test(db, test_id, current_user)


@router.patch("/{test_id}/edit-test", status_code=status.HTTP_200_OK)
def update_kiss24_test_details(test_id: str, payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.update_kiss24_test_details(db, test_id, payload, current_user)


@router.get("/{test_id}/live-status", status_code=status.HTTP_200_OK)
def get_kiss24_live_status(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.get_kiss24_live_status(db, test_id, current_user)


@router.get("/{test_id}/vulnerabilities", status_code=status.HTTP_200_OK)
def get_kiss24_vulnerabilities(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.get_kiss24_vulnerabilities(db, test_id, current_user)


@router.get("/vuln-types", status_code=status.HTTP_200_OK, summary="[Service Endpoint]")
def get_kiss24_vuln_types_for_dropdown(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.get_kiss24_vuln_types_for_dropdown(db)


@router.post("/{test_id}/vulnerabilities/publish", status_code=status.HTTP_200_OK)
def publish_vulnerability(test_id: str, payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.publish_vulnerability(db, test_id, payload, current_user)


@router.get("/validating-vulns", summary="Get Cached Validating Vulns (Instant)")
def get_validating_vulns(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.get_validating_vulns(db)


@router.post("/validating-vulns/sync", summary="Reconcile & Sync with KISS24")
def sync_validating_vulns(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.sync_validating_vulns(db, current_user)


@router.put("/validating-vulns/{uuid}", summary="Update Local Vuln Info")
def update_validating_vuln(uuid: str, payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return kiss24_service.update_validating_vuln(db, uuid, payload, current_user)


@router.post("/validating-vulns/{uuid}/analyze")
def start_ai_analysis(uuid: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin_or_pentester), db: Session = Depends(get_db)):
    user_api_key = kiss24_service.get_user_kiss24_key(db, str(current_user["id"]))
    background_tasks.add_task(kiss24_service.trigger_luigi_verification_pipeline, uuid, user_api_key)
    return {"message": "Luigi pipeline started"}


@router.get("/reconciliation-candidates", summary="[Admin] Get Unmapped Assets")
def get_reconciliation_candidates(limit: int = 0, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.get_reconciliation_candidates(db, limit)


@router.put("/reconciliation-candidates/{raw_asset_id}/archive", summary="[Admin] Hide asset from reconciliation")
def archive_reconciliation_candidate(raw_asset_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Marks a raw asset as not reconcilable so it no longer appears in the queue."""
    return kiss24_service.archive_reconciliation_candidate(db, raw_asset_id, current_user)


@router.post("/reconcile-asset", summary="[Admin] Manually Link Mario Asset to KISS24")
def reconcile_asset(payload: ReconcileAssetPayload, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.reconcile_asset(db, payload, current_user)


@router.post("/reconcile-asset/bulk", summary="[Admin] Bulk Link Mario Assets to KISS24")
def bulk_reconcile_assets(payload: BulkReconcileAssetPayload, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kiss24_service.bulk_reconcile_assets(db, payload, current_user)


@router.put("/reconciliation-candidates/bulk-archive", summary="[Admin] Bulk hide assets from reconciliation")
def bulk_archive_reconciliation_candidates(payload: BulkAssetRequest, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """Marks multiple raw assets as not reconcilable so they no longer appear in the queue."""
    return kiss24_service.bulk_archive_reconciliation_candidates(db, payload, current_user)


@router.get("/raw/synced/", summary="[Admin] Get all raw assets synced with Kiss24")
def get_kiss24_synced_raw_assets(
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    current_user: dict = Depends(require_admin), db: Session = Depends(get_db)
):
    """Returns a list of raw assets that have a Kiss24 ID."""
    return kiss24_service.get_kiss24_synced_raw_assets_paginated(
        db, current_user, page=page, limit=20, search=search, sort_by=sort_by, sort_dir=sort_dir
    )


@router.get("/tests/synced/", summary="[Admin] Get all tests synced with Kiss24")
def get_kiss24_synced_tests(
    page: int = Query(1, ge=1),
    search: Optional[str] = None,
    service_lane: Optional[str] = None,
    status: Optional[str] = None,
    sort_by: str = Query("name"),
    sort_dir: str = Query("asc"),
    current_user: dict = Depends(require_admin), db: Session = Depends(get_db)
):
    """Returns a list of tests that are mapped to a Kiss24 pentest."""
    return kiss24_service.get_kiss24_synced_tests_paginated(
        db, current_user, page=page, limit=20, search=search, service_lane=service_lane,
        status=status, sort_by=sort_by, sort_dir=sort_dir
    )