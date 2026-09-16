from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, BackgroundTasks, Query
from typing import Optional
from datetime import datetime
import anyio
from database import get_db_cursor
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
@router.get("/types")
def get_asset_types(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return asset_service.get_all_asset_types(cursor)


@router.post("/types/", summary="[Admin Only]")
def create_asset_type(at: AssetTypeBase, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return asset_service.create_asset_type(cursor, at, current_user)


@router.put("/types/{type_id}", summary="[Admin Only]")
def update_asset_type(type_id: str, at: AssetTypeBase, current_user: dict = Depends(require_admin),
                      cursor=Depends(get_db_cursor)):
    return asset_service.update_asset_type(cursor, type_id, at, current_user)


@router.delete("/types/{type_id}", summary="[Admin Only]")
def delete_asset_type(type_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    return asset_service.delete_asset_type(cursor, type_id, current_user)


###################################
# ---      RAW ASSETS         --- #
###################################
@router.get("/raw")
def get_raw_assets(
        page: int = Query(1, ge=1), limit: int = Query(50, ge=1, le=500),
        search: Optional[str] = None, country_id: Optional[str] = None,
        service_id: Optional[str] = None, category_id: Optional[str] = None,
        asset_type_id: Optional[str] = None, facing_internet: Optional[str] = None,
        business_critical: Optional[int] = None, status: Optional[str] = None,
        is_kpi: Optional[bool] = None, is_critical: Optional[bool] = None,
        sort_by: Optional[str] = "name", sort_dir: Optional[str] = "asc",
        current_user: dict = Depends(require_admin_or_read_only), cursor=Depends(get_db_cursor)
):
    return asset_service.get_paginated_raw_assets(
        cursor, page, limit, search, country_id, service_id, category_id,
        asset_type_id, facing_internet, business_critical, status, is_kpi, is_critical, sort_by, sort_dir
    )


@router.post("/raw", summary="[Admin Only]")
def create_manual_raw_asset(asset: RawAssetCreate, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.create_manual_raw_asset(cursor, asset, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.get("/raw/{raw_id}")
def get_single_raw_asset(raw_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return asset_service.get_single_raw_asset(cursor, raw_id, current_user)


@router.put("/raw/{raw_id}", summary="[Admin/Maintainer]")
def update_raw_asset(raw_id: str, asset: RawAssetCreate, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.update_raw_asset(cursor, raw_id, asset, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.delete("/raw/{raw_id}", summary="[Admin Only]")
def delete_raw_asset(raw_id: str, year: int = Query(default_factory=lambda: datetime.now().year),
                     background_tasks: BackgroundTasks = BackgroundTasks(),
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.delete_raw_asset(cursor, raw_id, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.put("/raw/{raw_id}/restore", summary="[Admin Only]")
def restore_raw_asset(raw_id: str, year: int = Query(default_factory=lambda: datetime.now().year),
                      background_tasks: BackgroundTasks = BackgroundTasks(),
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.restore_raw_asset(cursor, raw_id, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.post("/raw/bulk-delete", summary="[Admin Only]")
def bulk_delete_raw_assets(req: BulkAssetRequest, year: int = Query(default_factory=lambda: datetime.now().year),
                           background_tasks: BackgroundTasks = BackgroundTasks(),
                           current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.bulk_delete_raw_assets(cursor, req, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.post("/raw/import", summary="[Admin Only]", include_in_schema=False)
async def import_assets(file: UploadFile = File(...), background_tasks: BackgroundTasks = BackgroundTasks(),
                        current_user: dict = Depends(require_admin)):
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
@router.post("/promote", summary="[Admin Only]")
def promote_raw_assets_to_pool(req: BulkAssetRequest, background_tasks: BackgroundTasks,
                               current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.promote_raw_assets_to_pool(cursor, req, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.put("/bulk-service", summary="[Admin Only]")
def bulk_update_service_lane(req: BulkServiceUpdateRequest, background_tasks: BackgroundTasks,
                             current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.bulk_update_service_lane(cursor, req, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


###################################
# ---    ACTIVE ASSET POOL    --- #
###################################
@router.get("/")
def get_active_asset_pool(year: Optional[int] = None, current_user: dict = Depends(get_current_user),
                          cursor=Depends(get_db_cursor)):
    if not year:
        year = datetime.now().year
    return asset_service.get_active_asset_pool(cursor, year, current_user)


@router.delete("/{asset_id}", summary="[Admin Only]")
def remove_from_active_pool(asset_id: str, year: int, background_tasks: BackgroundTasks,
                            current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = asset_service.remove_from_active_pool(cursor, asset_id, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


###################################
# --- ServiceNow integrations --- #
###################################
@router.post("/servicenow", summary="[Admin Only]")
def trigger_snow_sync(payload: SnowSyncRequest, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin)):
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


@router.get("/servicenow/last-sync", summary="[Admin Only]")
def get_last_snow_sync(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT MAX(last_snow_sync) FROM raw_assets_snow_metadata")
    row = cursor.fetchone()
    return {"last_sync": row[0] if row and row[0] else None}