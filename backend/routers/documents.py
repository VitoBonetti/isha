from fastapi import APIRouter, Depends, Query
from typing import Optional
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import require_admin
from system_services import document_service

router = APIRouter(prefix="/api/documents", tags=["Documents"])

@router.get("/", summary="[Admin Only] Get all test documents with metadata")
def get_all_documents(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        search: Optional[str] = None,
        service_lane_id: Optional[str] = None,
        doc_type: Optional[str] = None,
        sort_by: str = Query("synced_at"),
        sort_dir: str = Query("desc"),
        current_user: dict = Depends(require_admin),
        db: Session = Depends(get_db)
):
    return document_service.get_all_documents(
        db, page, limit, search, service_lane_id, doc_type, sort_by, sort_dir
    )