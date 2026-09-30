from fastapi import APIRouter, Depends, status, BackgroundTasks, Query
from database import get_db
from typing import Optional
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_admin_or_pentester
from schema import ReconcileAssetPayload, BulkReconcileAssetPayload, BulkAssetRequest
from system_services import kiss24_service

router = APIRouter(prefix="/api/kiss24", tags=["Kiss24 Tools"])


@router.post("/sync-org-ids", status_code=status.HTTP_200_OK, summary="[Admin Only] Sync KISS24 Org IDs")
def sync_kiss24_org_ids(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Sync the Keep Secure organization IDs with the internal geographic data.

    This endpoint pulls the latest organization configurations from the KISS24 platform
    and aligns them with internal country and regional structures.
    """
    return kiss24_service.sync_kiss24_org_ids(db, current_user)


@router.post("/sync-asset-ids", status_code=status.HTTP_200_OK, summary="[Admin Only] Sync KISS24 Asset IDs")
def sync_kiss24_asset_ids(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Sync Keep Secure assets with internal raw assets using OneTrust integration.

    Validates and updates asset linkages between the local database and KISS24
    by cross-referencing their shared OneTrust ID as the primary key.
    """
    return kiss24_service.sync_kiss24_asset_ids(db, current_user)


@router.get("/assets/total-count", summary="[Admin Only] Get Total KISS24 Asset Count")
def get_kiss24_asset_count(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Retrieve the exact count of assets currently ingested in the KISS24 platform.

    Used primarily for health-check comparisons and synchronization metrics.
    """
    return kiss24_service.get_kiss24_asset_count(db, current_user)


@router.post("/assets/{raw_asset_id}/create", status_code=status.HTTP_200_OK,
             summary="[Admin Only] Provision Raw Asset in KISS24")
def create_kiss24_asset_endpoint(raw_asset_id: str, current_user: dict = Depends(require_admin),
                                 db: Session = Depends(get_db)):
    """
    Manually provision a specific internal Raw Asset into the Keep Secure 24 platform.

    This creates the corresponding entity in KISS24 and saves the returned external UUID
    into the local database to establish the link.
    """
    return kiss24_service.create_kiss24_asset(db, raw_asset_id, current_user)


@router.post("/sync-update-kiss24-snowid", status_code=status.HTTP_200_OK,
             summary="[Admin Only] Sync ServiceNow IDs to KISS24")
def sync_update_kiss24_snowid(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Update Keep Secure Assets with their corresponding ServiceNow tracking IDs.

    Pushes local ServiceNow configurations up to the external KISS24 asset entities
    for streamlined compliance tracking.
    """
    return kiss24_service.sync_update_kiss24_snowid(db, current_user)


@router.post("/sync-vuln-types", status_code=status.HTTP_200_OK,
             summary="[Admin Only] Sync Vulnerability Type Dictionary")
def sync_kiss24_vulnerability_types(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Synchronize the vulnerability taxonomy between platforms.

    Downloads the current active list of accepted vulnerability categorizations from KISS24
    and updates the local dictionary.
    """
    return kiss24_service.sync_kiss24_vulnerability_types(db, current_user)


@router.post("/sync-user-kiss24-uuid", status_code=status.HTTP_200_OK, summary="[Admin Only] Sync User UUIDs")
def sync_user_kiss24_uuid(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Sync the internal user table with Keep Secure user profiles.

    Matches internal users by email against the KISS24 active directory and stores their
    assigned external UUID locally.
    """
    return kiss24_service.sync_user_kiss24_uuid(db, current_user)


@router.get("/vuln-types", status_code=status.HTTP_200_OK, summary="Get KISS24 Vuln Types for UI")
def get_kiss24_vuln_types_for_dropdown(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the cached vulnerability taxonomy formatted specifically for frontend dropdowns.
    """
    return kiss24_service.get_kiss24_vuln_types_for_dropdown(db)


@router.post("/{test_id}/create-test", status_code=status.HTTP_200_OK, summary="Provision Test in KISS24")
def create_kiss24_test(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Formally instantiate an internal test record inside the external KISS24 platform.

    Generates the test container in Keep Secure and assigns the associated asset and pentesters.
    """
    return kiss24_service.create_kiss24_test(db, test_id, current_user)


@router.patch("/{test_id}/edit-test", status_code=status.HTTP_200_OK, summary="Update KISS24 Test Details")
def update_kiss24_test_details(test_id: str, payload: dict, current_user: dict = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    """
    Push metadata updates from a local test to its linked Keep Secure counterpart.
    """
    return kiss24_service.update_kiss24_test_details(db, test_id, payload, current_user)


@router.get("/{test_id}/live-status", status_code=status.HTTP_200_OK, summary="Get KISS24 Live Status")
def get_kiss24_live_status(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Perform a real-time fetch to retrieve the exact workflow phase of the test on KISS24.
    """
    return kiss24_service.get_kiss24_live_status(db, test_id, current_user)


@router.get("/{test_id}/vulnerabilities", status_code=status.HTTP_200_OK, summary="Get KISS24 Vulnerabilities")
def get_kiss24_vulnerabilities(test_id: str, current_user: dict = Depends(get_current_user),
                               db: Session = Depends(get_db)):
    """
    Retrieve all findings and vulnerabilities currently logged inside the associated KISS24 test.
    """
    return kiss24_service.get_kiss24_vulnerabilities(db, test_id, current_user)


@router.post("/{test_id}/vulnerabilities/publish", status_code=status.HTTP_200_OK, summary="Publish Finding to KISS24")
def publish_vulnerability(test_id: str, payload: dict, current_user: dict = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """
    Push a new, unverified vulnerability finding directly into the KISS24 platform.
    """
    return kiss24_service.publish_vulnerability(db, test_id, payload, current_user)


@router.post("/{test_id}/vulnerabilities/{vuln_uuid}/change-state", status_code=status.HTTP_200_OK,
             summary="Change Vuln Workflow State")
def change_vuln_state(test_id: str, vuln_uuid: str, payload: dict, current_user: dict = Depends(get_current_user),
                      db: Session = Depends(get_db)):
    """
    Update the lifecycle status of a single vulnerability (e.g., from 'Open' to 'Verified').
    """
    return kiss24_service.change_vuln_state(db, test_id, vuln_uuid, payload.get("state"), current_user)


@router.post("/{test_id}/vulnerabilities/bulk-change-state", status_code=status.HTTP_200_OK,
             summary="Bulk Change Vuln Workflow State")
def bulk_change_vuln_state(test_id: str, payload: dict, current_user: dict = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    """
    Update the lifecycle status of multiple vulnerabilities simultaneously to streamline test resolution.
    """
    return kiss24_service.bulk_change_vuln_state(db, test_id, payload.get("vuln_uuids", []), payload.get("state"),
                                                 current_user)


@router.get("/validating-vulns", summary="Get Cached Validating Vulns")
def get_validating_vulns(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Instantly returns all vulnerabilities currently flagged for internal validation from the local cache.
    """
    return kiss24_service.get_validating_vulns(db)


@router.post("/validating-vulns/sync", summary="Sync Validating Vulns with KISS24")
def sync_validating_vulns(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Query KISS24 for all vulnerabilities stuck in validation workflows and update the local database cache.
    """
    return kiss24_service.sync_validating_vulns(db, current_user)


@router.put("/validating-vulns/{uuid}", summary="Update Local Vuln Info")
def update_validating_vuln(uuid: str, payload: dict, current_user: dict = Depends(get_current_user),
                           db: Session = Depends(get_db)):
    """
    Modifies internal notes and verification metadata for a specific vulnerability.
    """
    return kiss24_service.update_validating_vuln(db, uuid, payload, current_user)


@router.post("/validating-vulns/{uuid}/analyze", summary="Start AI Validation Pipeline")
def start_ai_analysis(uuid: str, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin_or_pentester), db: Session = Depends(get_db)):
    """
    Trigger the Luigi AI agent to automatically review and verify the selected vulnerability.
    """
    user_api_key = kiss24_service.get_user_kiss24_key(db, str(current_user["id"]))
    background_tasks.add_task(kiss24_service.trigger_luigi_verification_pipeline, uuid, user_api_key)
    return {"message": "Luigi pipeline started"}


@router.get("/reconciliation-candidates", summary="[Admin Only] Get Unmapped Assets")
def get_reconciliation_candidates(limit: int = 0, current_user: dict = Depends(require_admin),
                                  db: Session = Depends(get_db)):
    """
    Identify and return a list of active internal assets that are missing a Keep Secure 24 identifier.
    """
    return kiss24_service.get_reconciliation_candidates(db, limit)


@router.put("/reconciliation-candidates/{raw_asset_id}/archive", summary="[Admin Only] Hide Asset from Reconciliation")
def archive_reconciliation_candidate(raw_asset_id: str, current_user: dict = Depends(require_admin),
                                     db: Session = Depends(get_db)):
    """
    Marks a raw asset as 'not reconcilable', permanently removing it from the unmapped queue.
    """
    return kiss24_service.archive_reconciliation_candidate(db, raw_asset_id, current_user)


@router.post("/reconcile-asset", summary="[Admin Only] Manually Link Asset to KISS24")
def reconcile_asset(payload: ReconcileAssetPayload, current_user: dict = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """
    Force a link between an internal Raw Asset and a specific KISS24 asset UUID.
    """
    return kiss24_service.reconcile_asset(db, payload, current_user)


@router.post("/reconcile-asset/bulk", summary="[Admin Only] Bulk Link Assets to KISS24")
def bulk_reconcile_assets(payload: BulkReconcileAssetPayload, current_user: dict = Depends(require_admin),
                          db: Session = Depends(get_db)):
    """
    Establish links for a batch of assets to their corresponding KISS24 UUIDs in one transaction.
    """
    return kiss24_service.bulk_reconcile_assets(db, payload, current_user)


@router.put("/reconciliation-candidates/bulk-archive", summary="[Admin Only] Bulk Hide Assets from Reconciliation")
def bulk_archive_reconciliation_candidates(payload: BulkAssetRequest, current_user: dict = Depends(require_admin),
                                           db: Session = Depends(get_db)):
    """
    Mark multiple raw assets as 'not reconcilable' simultaneously so they no longer appear in the queue.
    """
    return kiss24_service.bulk_archive_reconciliation_candidates(db, payload, current_user)


@router.get("/raw/synced/", summary="[Admin Only] Get Synced Raw Assets")
def get_kiss24_synced_raw_assets(
        page: int = Query(1, ge=1),
        search: Optional[str] = None,
        sort_by: str = Query("name"),
        sort_dir: str = Query("asc"),
        current_user: dict = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Retrieve a paginated, sortable list of all internal raw assets successfully mapped to a Kiss24 ID.
    """
    return kiss24_service.get_kiss24_synced_raw_assets_paginated(
        db, current_user, page=page, limit=20, search=search, sort_by=sort_by, sort_dir=sort_dir
    )


@router.get("/tests/synced/", summary="[Admin Only] Get Synced Tests")
def get_kiss24_synced_tests(
        page: int = Query(1, ge=1),
        search: Optional[str] = None,
        service_lane: Optional[str] = None,
        status: Optional[str] = None,
        sort_by: str = Query("name"),
        sort_dir: str = Query("asc"),
        current_user: dict = Depends(require_admin), db: Session = Depends(get_db)
):
    """
    Retrieve a paginated list of internal scheduled tests successfully mapped to a Kiss24 pentest ID.
    """
    return kiss24_service.get_kiss24_synced_tests_paginated(
        db, current_user, page=page, limit=20, search=search, service_lane=service_lane,
        status=status, sort_by=sort_by, sort_dir=sort_dir
    )