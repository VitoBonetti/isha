from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Response, status, Query
from pydantic import UUID4
from typing import Optional
import uuid
from datetime import datetime, timedelta
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin, require_write_access
from schema import EventCreate, EventBase, ServiceCategoryCreate, ServiceCategoryBase
from websockets_manager import manager
from audit_logger import log_audit_event

router = APIRouter(prefix="/api/danger", tags=["Danger Zone"])


@router.delete("/system/wipe", summary="[Admin Only]")
def wipe_system_data(background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint
    FACTORY RESET:
    Wipes all planning data (Tests, Assignments, Assets, Notifications, Categories, Regions, Countries).
    Preserves structural configurations (Users, Events, Locations).
    """
    try:
        cursor.execute("""
            TRUNCATE TABLE notifications CASCADE;
            TRUNCATE TABLE countries CASCADE;
            TRUNCATE TABLE regions CASCADE;
            TRUNCATE TABLE assignments CASCADE;
            TRUNCATE TABLE test_assets CASCADE;
            TRUNCATE TABLE tests CASCADE;
            TRUNCATE TABLE assets CASCADE;
            TRUNCATE TABLE raw_assets CASCADE;
            TRUNCATE TABLE services_lanes CASCADE;
            TRUNCATE TABLE service_categories CASCADE;
            TRUNCATE TABLE asset_history CASCADE;
            TRUNCATE TABLE test_history CASCADE;
        """)
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="FACTORY_RESET",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator successfully wiped all transactional data (Tests, Assignments, Assets)."
        )

        # Broadcast the wipe to all connected clients
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')

        return {"message": "System data wiped successfully."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe system data.")


@router.delete("/secrets-note/wipe-secrets", summary="[Admin Only]")
def wipe_all_secrets(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to wipe the secret_notes
    """
    cursor.execute("TRUNCATE TABLE secret_notes CASCADE;")

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="WIPE_SECRETS",
        resource_type="DATABASE",
        resource_id="N/A",
        details="Administrator wiped ALL encrypted secure notes."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "All secure notes wiped."}


@router.delete("/tests/wipe-google-drive-workspace", summary="[Admin Only]")
def wipe_drive_folders(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                       cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to unlink all Drive folders from tests and wipe the associated test documents.
    """
    try:
        # Unlink folders from tests
        cursor.execute("""
            UPDATE tests 
            SET drive_folder_id = NULL, drive_folder_url = NULL;
        """)

        # Wipe the documents table
        cursor.execute("TRUNCATE TABLE test_documents CASCADE;")

        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="WIPE_DRIVE_FOLDERS",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator unlinked all Google Drive folders from tests and wiped all document metadata."
        )

        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        return {"message": "All Google Drive folders unlinked and document metadata wiped."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe drive folders.")


@router.delete("/tests/wipe-documents", summary="[Admin Only]")
def wipe_all_documents(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                       cursor=Depends(get_db_cursor)):
    """
    Admin-Only endpoint to wipe only the test_documents table.
    """
    try:
        cursor.execute("TRUNCATE TABLE test_documents CASCADE;")
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="WIPE_DOCUMENTS",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator wiped all Google Drive document metadata."
        )

        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        return {"message": "All document metadata wiped successfully."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe documents.")

