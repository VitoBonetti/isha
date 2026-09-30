from fastapi import APIRouter, Depends, BackgroundTasks
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import require_admin
from websockets_manager import manager
from system_services import danger_service

router = APIRouter(prefix="/api/danger", tags=["Danger Zone"])


@router.delete("/system/wipe", summary="[Admin Only] Factory Reset System Data")
def wipe_system_data(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """
    FACTORY RESET: Wipes all planning data.

    This destructive endpoint clears out test schedules, assignments, and board events, resetting the operational planning data while preserving core dictionaries.
    """
    res = danger_service.wipe_system_data(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.delete("/secrets-note/wipe-secrets", summary="[Admin Only] Wipe All Secrets")
def wipe_all_secrets(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                     db: Session = Depends(get_db)):
    """
    Wipe all encrypted secret notes.

    Permanently deletes all stored secure notes and credentials linked to tests across the entire database.
    """
    res = danger_service.wipe_all_secrets(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-google-drive-workspace", summary="[Admin Only] Wipe Drive Folders")
def wipe_drive_folders(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                       db: Session = Depends(get_db)):
    """
    Unlink all Google Drive folders and wipe associated test documents.

    Detaches all workspace URLs from tests and clears the test documents table to reset the RAG state.
    """
    res = danger_service.wipe_drive_folders(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-orphan-documents", summary="[Admin Only] Wipe Orphan Documents")
def wipe_orphan_documents(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                          db: Session = Depends(get_db)):
    """
    Scan Google Drive and remove orphaned documents.

    Identifies and purges ghost files from the RAG database that no longer exist in the connected Google Drive workspaces.
    """
    res = danger_service.wipe_orphan_documents(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-documents", summary="[Admin Only] Wipe All Documents")
def wipe_all_documents(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                       db: Session = Depends(get_db)):
    """
    Wipe the test_documents table.

    Clears all indexed document metadata from the local database, forcing a fresh sync on the next run.
    """
    res = danger_service.wipe_all_documents(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-rag-chat-logs", summary="[Admin Only] Wipe RAG Chat Logs")
def wipe_all_rag_chat_logs(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                           db: Session = Depends(get_db)):
    """
    Wipe the rag_chat_logs table.

    Permanently deletes all conversational AI chat histories and context windows across all tests.
    """
    res = danger_service.wipe_all_rag_chat_logs(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/tests/wipe-test-analyses", summary="[Admin Only] Wipe Test Analyses")
def wipe_all_test_analyses(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                           db: Session = Depends(get_db)):
    """
    Wipe the test_analyses table.

    Permanently deletes all AI-generated vulnerability analyses and summaries.
    """
    res = danger_service.wipe_all_test_analyses(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/reset-asset-kpi-criteria", summary="[Admin Only] Reset Asset KPI Criteria")
def reset_asset_kpi_criteria(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                             db: Session = Depends(get_db)):
    """
    Reset KPI and Critical flags on raw assets.

    Bulk updates the raw_assets table, resetting the 'is_critical' and 'is_kpi' fields to False globally.
    """
    res = danger_service.reset_asset_kpi_criteria(db, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res