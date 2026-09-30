from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Query
from typing import Optional
from datetime import datetime
import anyio
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_maintainer_or_admin, require_admin_or_read_only
from schema import RawAssetCreate, AssetTypeBase, BulkAssetRequest, BulkServiceUpdateRequest, SnowSyncRequest
from starlette import status
from websockets_manager import manager
from audit_logger import log_audit_event
from system_services import asset_service

router = APIRouter(prefix="/api/assets", tags=["Assets"])


###################################
# --- ASSET TYPES DICTIONARY  --- #
###################################
@router.get(
    "/types",
    summary="Get Asset Types"
)
def get_asset_types(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve all active asset types.

    Fetches the complete dictionary of asset types available in the system.
    These types are used to categorize raw assets (e.g., Web Application, API, Mobile App, Infrastructure).
    """
    return asset_service.get_all_asset_types(db)


@router.post(
    "/types/",
    summary="[Admin Only] Create Asset Type"
)
def create_asset_type(at: AssetTypeBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Define a new asset type classification.

    Allows administrators to define a new asset type to categorize assets within the platform.
    Requires a unique name.
    """
    return asset_service.create_asset_type(db, at, current_user)


@router.put(
    "/types/{type_id}",
    summary="[Admin Only] Update Asset Type"
)
def update_asset_type(type_id: str, at: AssetTypeBase, current_user: dict = Depends(require_admin),
                      db: Session = Depends(get_db)):
    """
    Modify an existing asset type's properties.

    Modifies the properties (e.g., name, configuration) of a specific asset type using its unique ID.
    """
    return asset_service.update_asset_type(db, type_id, at, current_user)


@router.delete(
    "/types/{type_id}",
    summary="[Admin Only] Delete Asset Type"
)
def delete_asset_type(type_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Remove an asset type from the dictionary.

    Removes an asset type from the system. This action is restricted to administrators and
    may be blocked if active assets are currently relying on this type.
    """
    return asset_service.delete_asset_type(db, type_id, current_user)


###################################
# ---      RAW ASSETS         --- #
###################################
@router.get(
    "/raw",
    summary="Get Raw Assets"
)
def get_raw_assets(
        page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=500),
        search: Optional[str] = None, country_id: Optional[str] = None,
        service_id: Optional[str] = None, category_id: Optional[str] = None,
        asset_type_id: Optional[str] = None, facing_internet: Optional[str] = None,
        business_critical: Optional[int] = None, status: Optional[str] = None,
        is_kpi: Optional[bool] = None, is_critical: Optional[bool] = None,
        sort_by: Optional[str] = "name", sort_dir: Optional[str] = "asc",
        current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)
):
    """
    Retrieve a paginated and filtered list of raw assets.

    Retrieves raw assets from the database with robust support for extensive filtering
    (by country, service lane, category, type, criticality, internet exposure, etc.),
    dynamic sorting, and pagination.
    """
    return asset_service.get_paginated_raw_assets(
        db, page, limit, search, country_id, service_id, category_id,
        asset_type_id, facing_internet, business_critical, status, is_kpi, is_critical, sort_by, sort_dir
    )


@router.post(
    "/raw",
    summary="[Admin Only] Create Raw Asset"
)
def create_manual_raw_asset(asset: RawAssetCreate, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Manually insert a new raw asset into the database.

    Bypasses automated background imports and allows administrators to manually create
    a single raw asset. This action automatically triggers a UI refresh for connected clients via WebSockets.
    """
    res = asset_service.create_manual_raw_asset(db, asset, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.get(
    "/raw/{raw_id}",
    summary="Get Single Raw Asset Details"
)
def get_single_raw_asset(raw_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Fetch deep details for a specific raw asset.

    Retrieves the complete profile of a single raw asset based on its unique identifier.
    This includes all metadata, linked contacts, assigned service lanes, and historical data.
    """
    return asset_service.get_single_raw_asset(db, raw_id, current_user)


@router.put(
    "/raw/{raw_id}",
    summary="[Admin/Maintainer] Update Raw Asset"
)
def update_raw_asset(raw_id: str, asset: RawAssetCreate, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Modify the metadata and configurations of a specific raw asset.

    Allows Admins or assigned Maintainers to update the data of an existing raw asset.
    Triggers a WebSocket broadcast to refresh the asset boards of active users.
    """
    res = asset_service.update_raw_asset(db, raw_id, asset, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.delete(
    "/raw/{raw_id}",
    summary="[Admin Only] Delete Raw Asset"
)
def delete_raw_asset(raw_id: str, year: int = Query(default_factory=lambda: datetime.now().year),
                     background_tasks: BackgroundTasks = BackgroundTasks(),
                     current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Archive or soft-delete a raw asset.

    Performs a soft-delete on a raw asset for the specified context year.
    It removes the asset from active operational views without permanently destroying its historical audit records.
    """
    res = asset_service.delete_raw_asset(db, raw_id, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.put(
    "/raw/{raw_id}/restore",
    summary="[Admin Only] Restore Raw Asset"
)
def restore_raw_asset(raw_id: str, year: int = Query(default_factory=lambda: datetime.now().year),
                      background_tasks: BackgroundTasks = BackgroundTasks(),
                      current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Recover a previously soft-deleted raw asset.

    Recovers a deleted raw asset, making it active and visible in the platform's registries once again.
    """
    res = asset_service.restore_raw_asset(db, raw_id, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.post(
    "/raw/bulk-delete",
    summary="[Admin Only] Bulk Delete Raw Assets"
)
def bulk_delete_raw_assets(req: BulkAssetRequest, year: int = Query(default_factory=lambda: datetime.now().year),
                           background_tasks: BackgroundTasks = BackgroundTasks(),
                           current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Perform a soft-delete operation on multiple raw assets simultaneously.

    Accepts an array of raw asset IDs and efficiently processes a soft-delete across all of them
    in a single transaction. Broadcasts a UI refresh upon completion.
    """
    res = asset_service.bulk_delete_raw_assets(db, req, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.post(
    "/raw/import",
    summary="[Admin Only] Import Assets via Excel",
    include_in_schema=False
)
async def import_assets(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(),
                        current_user: dict = Depends(require_admin)):
    """
    Parse and ingest raw assets from a structured Excel spreadsheet.

    Processes an uploaded Excel file to import multiple raw assets synchronously.
    Includes strict security checks for MIME types, file signatures, and payload size limits to prevent abuse.
    """
    if file.content_type not in asset_service.ALLOWED_MIME_TYPES:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="File type not allowed")

    contents = b""
    while chunk := await file.read(1024 * 1024):
        contents += chunk
        if len(contents) > asset_service.MAX_FILE_SIZE:
            raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail="File too large")

    if not asset_service.is_valid_file_signature(contents, file.filename):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file signature")

    success_count, failed_items = await anyio.to_thread.run_sync(
        asset_service.process_excel_import_sync, contents, file.filename, current_user
    )

    if success_count > 0:
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')

    return {"message": "Import processed", "success": success_count, "failed": failed_items}


###################################
# ---  THE PROMOTION ENGINE   --- #
###################################
@router.post(
    "/promote",
    summary="[Admin Only] Promote Raw Assets"
)
def promote_raw_assets_to_pool(req: BulkAssetRequest, background_tasks: BackgroundTasks,
                               current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Elevate raw assets into the active testing pool.

    Takes a batch of Raw Assets and 'promotes' them into the Active Asset Pool.
    Once promoted, an asset can be formally scheduled for a penetration test or compliance review.
    """
    res = asset_service.promote_raw_assets_to_pool(db, req, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.put(
    "/bulk-service",
    summary="[Admin Only] Bulk Update Service Lanes"
)
def bulk_update_service_lane(req: BulkServiceUpdateRequest, background_tasks: BackgroundTasks,
                             current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Reassign multiple assets to a different Service Lane.

    Allows administrators to quickly re-route a batch of assets by assigning them a new
    Service Lane ID in a single database transaction.
    """
    res = asset_service.bulk_update_service_lane(db, req, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


###################################
# ---    ACTIVE ASSET POOL    --- #
###################################
@router.get(
    "/",
    summary="Get Active Asset Pool"
)
def get_active_asset_pool(year: Optional[int] = None, current_user: dict = Depends(get_current_user),
                          db: Session = Depends(get_db)):
    """
    Retrieve all assets currently promoted to the active testing pool.

    Fetches all assets that have been promoted into the active workspace for the given operational year.
    These are the assets actively mapped to the Kanban board and testing schedule.
    """
    if not year:
        year = datetime.now().year
    return asset_service.get_active_asset_pool(db, year, current_user)


@router.delete(
    "/{asset_id}",
    summary="[Admin Only] Demote Active Asset"
)
def remove_from_active_pool(asset_id: str, year: int, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Remove an asset from the active pool.

    Demotes an asset by pulling it out of the active testing pool for the specified year.
    It returns the asset to a strictly 'raw' state without deleting the underlying raw data.
    """
    res = asset_service.remove_from_active_pool(db, asset_id, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


###################################
# --- ServiceNow integrations --- #
###################################
@router.post(
    "/servicenow",
    summary="[Admin Only] Trigger CMDB Sync"
)
def trigger_snow_sync(payload: SnowSyncRequest, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin)):
    """
    Launch a background synchronization with the ServiceNow instance.

    Initiates an asynchronous background job to connect to the external ServiceNow CMDB.
    The job will fetch, deduplicate, process, and ingest active application assets without blocking the main API thread.
    """
    background_tasks.add_task(
        asset_service.full_background_sync_wrapper,
        str(current_user["id"]),
        str(current_user["role"])
    )
    log_audit_event(
        user_id=str(current_user["id"]), role=str(current_user["role"]), action="SNOW_SYNC_STARTED",
        resource_type="INTEGRATION", details="Admin manually triggered the ServiceNow CMDB sync."
    )
    return {"message": "ServiceNow sync started in the background. This may take a few minutes."}


@router.get(
    "/servicenow/last-sync",
    summary="[Admin Only] Get Last CMDB Sync Time"
)
def get_last_snow_sync(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Check the timestamp of the most recent successful ServiceNow synchronization.

    Retrieves the exact database timestamp indicating when the last background
    ServiceNow CMDB ingestion completed successfully. Used primarily by the frontend polling mechanism.
    """
    return asset_service.get_last_snow_sync(db, current_user)