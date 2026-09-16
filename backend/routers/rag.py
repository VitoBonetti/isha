import asyncio
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, BackgroundTasks
from pydantic import UUID4
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import require_admin
from schema import RagChatRequest, RagChatBulkDeleteRequest, FeedbackRequest
from audit_logger import log_audit_event
from system_services import rag_service

router = APIRouter(prefix="/api/rag", tags=["RAG Intelligence"])


@router.post("/knowledge-base/sync", summary="[Admin] Sync Global Knowledge Base")
def trigger_knowledge_base_sync(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin)):
    background_tasks.add_task(rag_service.sync_knowledge_base_background, str(current_user["id"]), str(current_user["role"]))
    log_audit_event(str(current_user["id"]), current_user["role"], "SYNC_KB_RAG_STARTED", "RAG", "KNOWLEDGE_BASE", "Manual sync initiated.")
    return {"message": "Knowledge Base sync started in the background."}


@router.get("/", summary="[Admin] Testing endpoint for check the chunck")
def check_chunks(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.check_all_chunks(db)


@router.post("/tests/{test_id}/sync", summary="[Admin] Sync test documents to AI Knowledge Base")
def sync_test_to_rag(test_id: UUID4, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin)):
    background_tasks.add_task(rag_service.process_test_documents_background, str(test_id), str(current_user["id"]), str(current_user["role"]))
    log_audit_event(str(current_user["id"]), current_user["role"], "SYNC_TEST_TO_RAG_STARTED", "RAG", str(test_id), f"Test sync started.")
    return {"message": "RAG synchronization started in the background."}


@router.post("/sync-all", summary="[Admin] Manually trigger full system Drive sync")
def trigger_global_rag_sync(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin)):
    background_tasks.add_task(rag_service.sync_all_active_tests_background, str(current_user["id"]), str(current_user["role"]))
    log_audit_event(str(current_user["id"]), current_user["role"], "SYNC_TEST_TO_RAG_STARTED", "RAG", "ALL TESTS", "Global RAG sync initiated.")
    return {"message": "Global RAG sync initiated in the background."}


async def start_nightly_rag_scheduler():
    """Runs the sync_all worker once every 24 hours at 02:00 AM UTC."""
    while True:
        now = datetime.now(timezone.utc)
        target = now.replace(hour=2, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target.replace(day=now.day + 1)
        await asyncio.sleep((target - now).total_seconds())
        await asyncio.to_thread(rag_service.sync_all_active_tests_background, "SYSTEM", "SYSTEM")


@router.get("/filters", summary="Get autocomplete filters for RAG chat")
def get_rag_filters(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.get_rag_filters(db)


@router.get("/stats", summary="Get RAG knowledge base statistics")
def get_rag_stats(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.get_rag_stats(db)


@router.post("/chat", summary="Query the RAG Knowledge Base (Streaming)")
def chat_with_documents(req: RagChatRequest, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.chat_with_documents(db, req, current_user)


@router.get('/rag_chat_logs', summary='{Admin only] Rag Chat Logs')
def rag_chat_logs(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.get_all_rag_logs(db)


@router.get("/sessions", summary="Get user chat sessions")
def get_chat_sessions(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.get_chat_sessions(db, current_user)


@router.get("/sessions/{session_id}", summary="Get messages for a specific session")
def get_session_messages(session_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.get_session_messages(db, session_id, current_user)


@router.post("/logs/{log_id}/feedback", summary="Submit feedback for a response")
def submit_rag_feedback(log_id: str, request: FeedbackRequest, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.submit_rag_feedback(db, log_id, request, current_user)


@router.delete("/sessions/{session_id}", summary="Soft delete a single chat session")
def delete_chat_session(session_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.delete_chat_session(db, session_id, current_user)


@router.post("/sessions/bulk-delete", summary="Soft delete multiple chat sessions")
def bulk_delete_chat_sessions(request: RagChatBulkDeleteRequest, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.bulk_delete_chat_sessions(db, request, current_user)


@router.get("/sessions/shared/{session_id}", summary="Get messages for a shared session (Read-Only)")
def get_shared_session_messages(session_id: str, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return rag_service.get_shared_session_messages(db, session_id)