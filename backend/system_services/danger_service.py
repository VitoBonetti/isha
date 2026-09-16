from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text
from models.tests import Tests, TestDocuments
from models.raw_assets import RawAssets, AssetCriteria
from audit_logger import log_audit_event


def wipe_system_data(db: Session, current_user: dict):
    try:
        # Use text() to safely execute raw DDL statements through the SQLAlchemy Session
        db.execute(text("""
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
        """))
        db.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="FACTORY_RESET",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator successfully wiped all transactional data (Tests, Assignments, Assets)."
        )
        return {"message": "System data wiped successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe system data.")


def wipe_all_secrets(db: Session, current_user: dict):
    db.execute(text("TRUNCATE TABLE secret_notes CASCADE;"))
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="WIPE_SECRETS",
        resource_type="DATABASE",
        resource_id="N/A",
        details="Administrator wiped ALL encrypted secure notes."
    )
    return {"message": "All secure notes wiped."}


def wipe_drive_folders(db: Session, current_user: dict):
    try:
        # Pure SQLAlchemy Bulk Update
        db.query(Tests).update(
            {Tests.drive_folder_id: None, Tests.drive_folder_url: None},
            synchronize_session=False
        )

        db.execute(text("TRUNCATE TABLE test_documents CASCADE;"))
        db.execute(text("TRUNCATE TABLE test_analyses CASCADE;"))
        db.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="WIPE_DRIVE_FOLDERS",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator unlinked all Google Drive folders from tests and wiped all document metadata."
        )
        return {"message": "All Google Drive folders unlinked and document metadata wiped."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe drive folders.")


def wipe_all_documents(db: Session, current_user: dict):
    try:
        db.execute(text("TRUNCATE TABLE test_documents CASCADE;"))
        db.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="WIPE_DOCUMENTS",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator wiped all Google Drive document metadata."
        )
        return {"message": "All document metadata wiped successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe documents.")


def wipe_all_rag_chat_logs(db: Session, current_user: dict):
    try:
        db.execute(text("TRUNCATE TABLE rag_chat_logs CASCADE;"))
        db.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="WIPE_RAG_CHAT_LOGS",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator wiped all rag chat logs."
        )
        return {"message": "All rag chat logs wiped successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe rag chat logs.")


def wipe_all_test_analyses(db: Session, current_user: dict):
    try:
        db.execute(text("TRUNCATE TABLE test_analyses CASCADE;"))

        # Pure SQLAlchemy Bulk Delete
        db.query(TestDocuments).filter(TestDocuments.is_virtual == True).delete(synchronize_session=False)
        db.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="WIPE_TEST_ANALYSIS",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator wiped all test_analyses."
        )
        return {"message": "All test_analyses wiped successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe test_analyses.")


def reset_asset_kpi_criteria(db: Session, current_user: dict):
    try:
        # Pure SQLAlchemy Bulk Updates
        db.query(RawAssets).update(
            {RawAssets.is_kpi: False, RawAssets.is_critical: False},
            synchronize_session=False
        )
        db.query(AssetCriteria).update(
            {AssetCriteria.is_evaluated: False},
            synchronize_session=False
        )

        db.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="RESET_KPI_CRITERIA_FROM_RAW_ASSETS",
            resource_type="RAW_ASSETS",
            resource_id="N/A",
            details="Administrator reset all KPI Criteria from the raw_assets table."
        )
        return {"message": "All KPI Criteria from the raw_assets table reset successfully."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail="Failed to reset KPI Criteria from the raw_assets.")