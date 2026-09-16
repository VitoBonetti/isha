import json
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request as FastAPIRequest
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_maintainer_or_admin
from schema import SendEmailPayload, MeetingProposalRequest
from websockets_manager import manager
from system_services import luigi_service

router = APIRouter(prefix="/api/luigi", tags=["Luigi"])


def verify_luigi_token(request: FastAPIRequest):
    """
    Enforces that Luigi's callbacks are authenticated via IAP or Bearer Token.
    """
    iap_jwt = request.headers.get("x-goog-iap-jwt-assertion")
    auth_header = request.headers.get("Authorization")

    if not iap_jwt and not (auth_header and auth_header.startswith("Bearer ")):
        raise HTTPException(
            status_code=401,
            detail="Missing IAP Assertion or IAM Bearer Token (Blocked by Backend)"
        )
    return iap_jwt or auth_header.split(" ")[1]


# ================================
# --- 1. INTRO EMAIL ENDPOINTS ---
# ================================
@router.get("/{test_id}/draft-intro-email", summary="[Admin/Maintainer]")
def draft_intro_email(test_id: str, current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    return luigi_service.draft_intro_email(db, test_id, current_user)


@router.post("/{test_id}/send-intro-email", summary="[Admin/Maintainer]")
def send_intro_email(test_id: str, payload: SendEmailPayload, current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    return luigi_service.send_intro_email(db, test_id, payload, current_user)


# ================================
# --- 2. FINAL EMAIL ENDPOINTS ---
# ================================
@router.get("/{test_id}/draft-final-email")
def draft_final_email(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return luigi_service.draft_final_email(db, test_id, current_user)


@router.post("/{test_id}/send-final-email")
def send_final_email(test_id: str, payload: SendEmailPayload, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return luigi_service.send_final_email(db, test_id, payload, current_user)


# =======================================
# --- 3. MEETING SCHEDULING ENDPOINTS ---
# =======================================
@router.get("/{test_id}/meeting-participants")
def get_meeting_participants(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return luigi_service.get_meeting_participants(db, test_id, current_user)


@router.post("/{test_id}/request-meeting-proposals")
def request_meeting_proposals(test_id: str, payload: MeetingProposalRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return luigi_service.request_meeting_proposals(db, test_id, payload, current_user)


@router.post("/save-meeting-proposals")
async def receive_meeting_proposals(payload: dict, token: str = Depends(verify_luigi_token)):
    await manager.broadcast(json.dumps({
        "action": "MEETING_PROPOSALS_READY",
        "email": payload.get("user_email"),
        "test_id": payload.get("test_id"),
        "test_name": payload.get("test_name"),
        "meeting_type": payload.get("meeting_type"),
        "proposals": payload.get("proposals"),
        "emails": payload.get("emails")
    }))
    return {"status": "success"}


@router.post("/{test_id}/book-meeting")
def book_meeting(test_id: str, payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return luigi_service.book_meeting(db, test_id, payload, current_user)


# =================================
# --- 4. VULNERABILITY DRAFTING ---
# =================================
@router.post("/draft-vulnerability")
def trigger_luigi_draft(payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return luigi_service.trigger_luigi_draft(db, payload, current_user)


@router.post("/vuln-draft-callback")
def luigi_draft_callback(payload: dict, background_tasks: BackgroundTasks, token: str = Depends(verify_luigi_token)):
    background_tasks.add_task(manager.broadcast, json.dumps({
        "action": "VULN_DRAFT_READY",
        "email": payload.get("user_email"),
        "html": payload.get("html"),
        "suggested_type": payload.get("suggested_type"),
        "mitre_id": payload.get("mitre_id", "")
    }))
    return {"status": "success"}


# ===========================
# --- 5. VALIDATION QUEUE ---
# ===========================
@router.post("/validation-callback", summary="Webhook for Luigi's Validation Verdict")
async def luigi_validation_callback(payload: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db), token: str = Depends(verify_luigi_token)):
    res, gcs_uris = luigi_service.process_validation_callback(db, payload)
    if gcs_uris:
        background_tasks.add_task(luigi_service.cleanup_temp_evidence, gcs_uris)
    await manager.broadcast(json.dumps({"action": "REFRESH_BOARD"}))
    return res