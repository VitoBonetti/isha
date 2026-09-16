from fastapi import APIRouter, Depends, BackgroundTasks
from database import get_db_cursor
from routers.auth import require_admin
from websockets_manager import manager
from system_services import danger_service

router = APIRouter(prefix="/api/danger", tags=["Danger Zone"])


@router.delete("/system/wipe", summary="[Admin Only]")
def wipe_system_data(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint
    FACTORY RESET: Wipes all planning data.
    """
    res = danger_service.wipe_system_data(cursor, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.delete("/secrets-note/wipe-secrets", summary="[Admin Only]")
def wipe_all_secrets(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to wipe the secret_notes
    """
    res = danger_service.wipe_all_secrets(cursor, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-google-drive-workspace", summary="[Admin Only]")
def wipe_drive_folders(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to unlink all Drive folders from tests and wipe the associated test documents.
    """
    res = danger_service.wipe_drive_folders(cursor, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-documents", summary="[Admin Only]")
def wipe_all_documents(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to wipe only the test_documents table.
    """
    res = danger_service.wipe_all_documents(cursor, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-rag-chat-logs", summary="[Admin Only]")
def wipe_all_rag_chat_logs(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to wipe only the rag_chat_logs table.
    """
    res = danger_service.wipe_all_rag_chat_logs(cursor, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-test-analyses", summary="[Admin Only]")
def wipe_all_test_analyses(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to wipe only the test_analyses table.
    """
    res = danger_service.wipe_all_test_analyses(cursor, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/reset-asset-kpi-criteria", summary="[Admin Only]")
def reset_asset_kpi_criteria(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to Reset is_critical and is_kpi field of raw_assets table to False
    """
    res = danger_service.reset_asset_kpi_criteria(cursor, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res