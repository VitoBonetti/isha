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
@router.get(
    "/{test_id}/draft-intro-email",
    summary="[Admin/Maintainer] Draft Intro Email"
)
def draft_intro_email(test_id: str, current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Request the Luigi AI to compose a kickoff/introductory email.

    Luigi extracts the test scope, assigned pentesters, and asset stakeholders to dynamically
    generate an HTML-formatted intro email customized to the service lane's templates.
    """
    return luigi_service.draft_intro_email(db, test_id, current_user)


@router.post(
    "/{test_id}/send-intro-email",
    summary="[Admin/Maintainer] Send Intro Email"
)
def send_intro_email(test_id: str, payload: SendEmailPayload, current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Dispatch the generated kickoff email.

    Takes the approved HTML payload and dispatches it via the configured Google Workspace
    service account to all primary contacts and stakeholders.
    """
    return luigi_service.send_intro_email(db, test_id, payload, current_user)


# ================================
# --- 2. FINAL EMAIL ENDPOINTS ---
# ================================
@router.get(
    "/{test_id}/draft-final-email",
    summary="Draft Final Output Email"
)
def draft_final_email(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Request the Luigi AI to compose a project closure email.

    Luigi synthesizes the testing outcomes, High/Critical vulnerabilities (if any),
    and the final PDF report link to construct an executive summary email.
    """
    return luigi_service.draft_final_email(db, test_id, current_user)


@router.post(
    "/{test_id}/send-final-email",
    summary="Send Final Output Email"
)
def send_final_email(test_id: str, payload: SendEmailPayload, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Dispatch the finalized closing email.

    Sends the project closure report to all required contacts via the Google Workspace API.
    """
    return luigi_service.send_final_email(db, test_id, payload, current_user)


# =======================================
# --- 3. MEETING SCHEDULING ENDPOINTS ---
# =======================================
@router.get(
    "/{test_id}/meeting-participants",
    summary="Get Default Meeting Participants"
)
def get_meeting_participants(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the exact list of internal pentesters and external asset stakeholders
    that should be invited to a project meeting based on the test's linkages.
    """
    return luigi_service.get_meeting_participants(db, test_id, current_user)


@router.post(
    "/{test_id}/request-meeting-proposals",
    summary="Request Calendar AI Proposals"
)
def request_meeting_proposals(test_id: str, payload: MeetingProposalRequest, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Trigger the AI Calendar Engine.

    Luigi scans the Google Calendars of all provided emails, cross-references internal
    timezones, and identifies the best available overlapping timeslots.
    """
    return luigi_service.request_meeting_proposals(db, test_id, payload, current_user)


@router.post(
    "/save-meeting-proposals",
    summary="[Webhook] Receive AI Calendar Proposals"
)
async def receive_meeting_proposals(payload: dict, token: str = Depends(verify_luigi_token)):
    """
    Internal Webhook for the Luigi worker.

    Once Luigi finishes crunching calendar availability, it POSTs the results back here.
    The endpoint instantly broadcasts the proposed timeslots to the initiating user's UI via WebSockets.
    """
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


@router.post(
    "/{test_id}/book-meeting",
    summary="Book Proposed Meeting Slot"
)
def book_meeting(test_id: str, payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Finalize and book a calendar event.

    Takes a timeslot generated by Luigi and formally dispatches calendar invites
    via Google Workspace to all requested participants.
    """
    return luigi_service.book_meeting(db, test_id, payload, current_user)


# =================================
# --- 4. VULNERABILITY DRAFTING ---
# =================================
@router.post(
    "/draft-vulnerability",
    summary="Draft AI Vulnerability Writeup"
)
def trigger_luigi_draft(payload: dict, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Trigger Luigi to draft a technical vulnerability report.

    Pentesters submit bullet points or raw logs. Luigi expands them into a professional,
    formatted markdown finding matching the platform's reporting standards.
    """
    return luigi_service.trigger_luigi_draft(db, payload, current_user)


@router.post(
    "/vuln-draft-callback",
    summary="[Webhook] Receive AI Vulnerability Draft"
)
def luigi_draft_callback(payload: dict, background_tasks: BackgroundTasks, token: str = Depends(verify_luigi_token)):
    """
    Internal Webhook for Luigi's vulnerability writer.

    Once the LLM finishes generating the technical writeup, it posts it here,
    and it is broadcasted directly back to the Pentester's active browser session.
    """
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
@router.post(
    "/validation-callback",
    summary="[Webhook] Receive AI Validation Verdict"
)
async def luigi_validation_callback(payload: dict, background_tasks: BackgroundTasks, db: Session = Depends(get_db), token: str = Depends(verify_luigi_token)):
    """
    Internal Webhook for the Luigi Validation Agent.

    When Luigi is asked to auto-verify a finding via uploaded evidence, it processes
    the result here, updates the vulnerability status in KISS24, and initiates a cleanup
    of temporary Google Cloud Storage evidence files.
    """
    res, gcs_uris = luigi_service.process_validation_callback(db, payload)
    if gcs_uris:
        background_tasks.add_task(luigi_service.cleanup_temp_evidence, gcs_uris)
    await manager.broadcast(json.dumps({"action": "REFRESH_BOARD"}))
    return res