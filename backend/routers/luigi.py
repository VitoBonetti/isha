import google.auth
from google.auth.transport.requests import Request
from google.cloud import pubsub_v1, storage
from datetime import datetime, timedelta, timezone
import json
import requests
import os
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, status, Request as FastAPIRequest
from utils.secret_manager import get_secret
from schema import SendEmailPayload, MeetingProposalRequest, LuigiVulnCallback
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin, require_write_access
from audit_logger import log_audit_event
from websockets_manager import manager

router = APIRouter(prefix="/api/luigi", tags=["Luigi"])

WEB_APP_URL = os.environ.get("LUIGI_MIDDLEWARE_CONTACTS_URL")
LUIGI_MIDDLEWARE_KEY_NAME = get_secret(os.environ.get("LUIGI_MIDDLEWARE_KEY_NAME"))
PUBSUB_TOPIC_PATH = os.environ.get("PUBSUB_TOPIC_PATH")


def verify_luigi_token(request: FastAPIRequest):
    """
    Enforces that Luigi's callbacks are authenticated.
    When behind GCP IAP, the original Authorization header is stripped,
    and IAP injects 'x-goog-iap-jwt-assertion' after successful authentication.
    """
    # 1. Check for the header injected by GCP IAP (Production)
    iap_jwt = request.headers.get("x-goog-iap-jwt-assertion")

    # 2. Fallback to standard Authorization header (Local Development)
    auth_header = request.headers.get("Authorization")

    if not iap_jwt and not (auth_header and auth_header.startswith("Bearer ")):
        raise HTTPException(
            status_code=401,
            detail="Missing IAP Assertion or IAM Bearer Token (Blocked by Backend)"
        )

    # Return whichever token was used so the route can proceed
    return iap_jwt or auth_header.split(" ")[1]


# --- Helper function for GCS Cleanup ---
def cleanup_temp_evidence(uris: list):
    if not uris:
        return
    try:
        storage_client = storage.Client()
        for uri in uris:
            parts = uri.replace("gs://", "").split("/", 1)
            if len(parts) == 2:
                bucket = storage_client.bucket(parts[0])
                blob = bucket.blob(parts[1])
                if blob.exists():
                    blob.delete()
                    print(f"🗑️ Cleaned up temp file: {uri}")
    except Exception as e:
        print(f"🚨 Failed to clean up temp bucket: {e}")


# ==========================================
# --- 1. INTRO EMAIL ENDPOINTS ---
# ==========================================
@router.get("/{test_id}/draft-intro-email", summary="[Admin Only]")
def draft_intro_email(test_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Draft Intro Email
    1. Fetch Test, Asset, Country, and Service data using the correct junction tables
    2. Fetch Pentesters using the correct Assignments table
    3. Calculate the start date (Monday of the given week/year)
    4. Fetch the REAL Contacts! (Using BOTH CountryContacts and RawAssetContacts)
    5. Populate Template
    """
    # 1. Fetch Test, Asset, Country, and Service data using the correct junction tables
    cursor.execute("""
            SELECT t.name, t.start_week, t.start_year,
                   a.name as asset_name, 
                   c.code as country_code, 
                   s.name as service_name, s.intro_email_template, s.auto_provision_workspace
            FROM tests t
            LEFT JOIN services_lanes s ON t.service_lane_id = s.id
            LEFT JOIN test_assets ta ON t.id = ta.test_id
            LEFT JOIN assets a ON ta.asset_id = a.id
            LEFT JOIN countries c ON a.country_id = c.id
            WHERE t.id = %s
            LIMIT 1
        """, (test_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Test not found")

    t_name, t_week, t_year, asset_name, country_code, service_name, db_template, auto_provision = row

    # template check  --> need error toast notification
    if not db_template:
        raise HTTPException(
            status_code=400,
            detail=f"No Intro Email Template is configured for the '{service_name}' service lane. Please add one in settings."
        )

    # 2. Fetch Pentesters using the correct Assignments table
    cursor.execute("""
            SELECT DISTINCT u.name, u.email 
            FROM assignments a
            JOIN users u ON a.user_id = u.id
            WHERE a.test_id = %s
        """, (test_id,))
    pentester_rows = cursor.fetchall()

    pentesters = ", ".join([r[0] for r in pentester_rows if r[0]])
    pentester_emails = set([r[1] for r in pentester_rows if r[1]])

    # 3. Calculate the start date (Monday of the given week/year)
    start_date_str = "TBD"
    if t_year and t_week:
        try:
            start_date = datetime.strptime(f'{t_year} {t_week} 1', "%G %V %u")
            start_date_str = start_date.strftime("%B %d, %Y")
        except:
            pass

    # 4. Fetch the REAL Contacts! (Merging Country and Asset Level Contacts)
    cursor.execute("""
        SELECT c.email, cc.is_developer, cc.is_stakeholder
        FROM test_assets ta
        JOIN assets a ON ta.asset_id = a.id
        JOIN country_contacts cc ON a.country_id = cc.country_id
        JOIN contacts c ON cc.contact_id = c.id
        WHERE ta.test_id = %s

        UNION

        SELECT c.email, rac.is_developer, rac.is_stakeholder
        FROM test_assets ta
        JOIN assets a ON ta.asset_id = a.id
        JOIN raw_asset_contacts rac ON a.raw_asset_id = rac.raw_asset_id
        JOIN contacts c ON rac.contact_id = c.id
        WHERE ta.test_id = %s
    """, (test_id, test_id))

    dev_emails = set()
    stakeholder_emails = set()

    for email, is_dev, is_stake in cursor.fetchall():
        if email:
            if is_dev: dev_emails.add(email)
            if is_stake: stakeholder_emails.add(email)

    # Routing Logic for TO and CC
    to_list = list(dev_emails)
    cc_list = list(stakeholder_emails) + list(pentester_emails)

    if not to_list:
        to_list = list(stakeholder_emails)
        cc_list = list(pentester_emails)

    if not to_list:
        to_list = list(pentester_emails)
        cc_list = []

    # Ensure no duplicates between To and CC
    cc_list = list(set(cc_list) - set(to_list))

    to_email = ", ".join(to_list)
    cc_emails = ", ".join(cc_list)

    # 5. Populate Template
    body = db_template.replace("{{service_lane}}", service_name or "Service")
    body = body.replace("{{country_code}}", country_code or "Country")
    body = body.replace("{{asset_name}}", asset_name or "Asset")
    body = body.replace("{{week}}", str(t_week) or "TBD")
    body = body.replace("{{year}}", str(t_year) or "TBD")
    body = body.replace("{{week_start_date}}", start_date_str)
    body = body.replace("{{pentesters}}", pentesters or "TBD")

    subject = f"Security Pentest Setup: {country_code or ''} - {asset_name or ''} (Week {t_week or ''})"

    return {
        "to": to_email,
        "cc": cc_emails,
        "subject": subject,
        "body": body
    }


@router.post("/{test_id}/send-intro-email", summary="[Admin Only]")
def send_intro_email(test_id: str, payload: SendEmailPayload, current_user: dict = Depends(require_admin),
                     cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Send Intro Email
    """

    if not payload.to and not payload.cc:
        raise HTTPException(status_code=400, detail="At least one recipient (To or CC) is required.")

    # We combine To and CC for Apps Script (GmailApp handles commas)
    all_recipients = payload.to
    if payload.cc:
        all_recipients += f",{payload.cc}"

    luigi_payload = {
        "secret_key": LUIGI_MIDDLEWARE_KEY_NAME,
        "action": "SEND_EMAIL",
        "to": all_recipients,
        "subject": payload.subject,
        "htmlBody": payload.body
    }

    response = requests.post(WEB_APP_URL, json=luigi_payload)
    response.raise_for_status()

    luigi_result = response.json()
    if luigi_result.get("success") is False:
        error_msg = luigi_result.get("error", "Unknown Apps Script error")
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="LUIGI_FIRST_EMAIL",
            resource_type="LUIGI",
            resource_id="N/A",
            details=f"Luigi Error: {error_msg}",
        )
        raise HTTPException(status_code=400, detail=f"Luigi failed: {error_msg}")

    # 2. Mark the Milestone as complete!
    cursor.execute("""
        INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
        VALUES (gen_random_uuid(), %s, 'Information Email Sent', true)
        ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true
    """, (test_id,))
    cursor.connection.commit()

    return {"status": "Success"}


# ==========================================
# --- 2. FINAL EMAIL ENDPOINTS ---
# ==========================================
@router.get("/{test_id}/draft-final-email")
def draft_final_email(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Endpoint to Draft Final Email
    1. Fetch Test, Asset, Country, Service data, AND kiss24
    2. Fetch Pentesters (Names AND Emails)
    3. Fetch the REAL Contacts (Using BOTH CountryContacts and RawAssetContacts)
    4. Populate Template
    """
    # 1. Fetch Test, Asset, Country, Service data, AND kiss24
    cursor.execute("""
        SELECT t.name, t.start_week, t.start_year, t.kiss24,
               a.name as asset_name, 
               c.code as country_code, 
               s.name as service_name, s.final_email_template
        FROM tests t
        LEFT JOIN services_lanes s ON t.service_lane_id = s.id
        LEFT JOIN test_assets ta ON t.id = ta.test_id
        LEFT JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN countries c ON a.country_id = c.id
        WHERE t.id = %s
        LIMIT 1
    """, (test_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Test not found")

    t_name, t_week, t_year, kiss24, asset_name, country_code, service_name, db_template = row

    # STRICT TEMPLATE CHECK:
    if not db_template:
        raise HTTPException(
            status_code=400,
            detail=f"No Final Email Template is configured for the '{service_name}' service lane. Please add one via API."
        )

    # 2. Fetch Pentesters (Names AND Emails)
    cursor.execute("""
        SELECT DISTINCT u.name, u.email 
        FROM assignments a
        JOIN users u ON a.user_id = u.id
        WHERE a.test_id = %s
    """, (test_id,))
    pentester_rows = cursor.fetchall()
    pentesters = ", ".join([r[0] for r in pentester_rows if r[0]])
    pentester_emails = set([r[1] for r in pentester_rows if r[1]])

    # 3. Fetch the REAL Contacts (Merging Country and Asset Level Contacts)
    cursor.execute("""
        SELECT c.email, cc.is_developer, cc.is_stakeholder
        FROM test_assets ta
        JOIN assets a ON ta.asset_id = a.id
        JOIN country_contacts cc ON a.country_id = cc.country_id
        JOIN contacts c ON cc.contact_id = c.id
        WHERE ta.test_id = %s

        UNION

        SELECT c.email, rac.is_developer, rac.is_stakeholder
        FROM test_assets ta
        JOIN assets a ON ta.asset_id = a.id
        JOIN raw_asset_contacts rac ON a.raw_asset_id = rac.raw_asset_id
        JOIN contacts c ON rac.contact_id = c.id
        WHERE ta.test_id = %s
    """, (test_id, test_id))

    dev_emails = set()
    stakeholder_emails = set()

    for email, is_dev, is_stake in cursor.fetchall():
        if email:
            if is_dev: dev_emails.add(email)
            if is_stake: stakeholder_emails.add(email)

    # Routing Logic for TO and CC
    to_list = list(dev_emails)
    cc_list = list(stakeholder_emails) + list(pentester_emails)

    if not to_list:
        to_list = list(stakeholder_emails)
        cc_list = list(pentester_emails)

    if not to_list:
        to_list = list(pentester_emails)
        cc_list = []

    # Ensure no duplicates between To and CC
    cc_list = list(set(cc_list) - set(to_list))

    to_email = ", ".join(to_list)
    cc_emails = ", ".join(cc_list)

    # 4. Populate Template
    body = db_template.replace("{{service_lane}}", service_name or "Service")
    body = body.replace("{{country_code}}", country_code or "Country")
    body = body.replace("{{asset_name}}", asset_name or "Asset")
    body = body.replace("{{week}}", str(t_week) or "TBD")
    body = body.replace("{{year}}", str(t_year) or "TBD")
    body = body.replace("{{pentesters}}", pentesters or "TBD")
    body = body.replace("{{kiss24}}", str(kiss24) if kiss24 else "MISSING_KISS24_ID")

    subject = f"Pentest Completed: {country_code or ''} - {asset_name or ''} ({service_name or ''})"

    return {
        "to": to_email,
        "cc": cc_emails,
        "subject": subject,
        "body": body
    }


@router.post("/{test_id}/send-final-email")
def send_final_email(test_id: str, payload: SendEmailPayload, current_user: dict = Depends(get_current_user),
                     cursor=Depends(get_db_cursor)):
    """
    Endpoint to Send Final Email
    """
    if not payload.to and not payload.cc:
        raise HTTPException(status_code=400, detail="At least one recipient (To or CC) is required.")

    cursor.execute("SELECT drive_folder_id FROM tests WHERE id = %s", (test_id,))
    folder_row = cursor.fetchone()
    if not folder_row or not folder_row[0]:
        raise HTTPException(status_code=400,
                            detail="No Google Drive Workspace found for this test. Cannot attach reports.")

    cursor.execute("""
            SELECT drive_file_id, file_name, mime_type 
            FROM test_documents 
            WHERE test_id = %s 
            ORDER BY last_modified DESC
        """, (test_id,))

    documents = cursor.fetchall()

    pdf_id = None
    ppt_id = None

    for doc in documents:
        doc_id, file_name, mime_type = doc
        name_lower = file_name.lower()

        # Match PDF
        if not pdf_id and (mime_type == 'application/pdf' or name_lower.endswith('.pdf')):
            pdf_id = doc_id

        if not ppt_id and (
                mime_type == 'application/vnd.google-apps.presentation' or
                mime_type == 'application/vnd.openxmlformats-officedocument.presentationml.presentation' or
                mime_type == 'application/vnd.ms-powerpoint' or
                name_lower.endswith(('.ppt', '.pptx'))
        ):
            ppt_id = doc_id

    if not pdf_id or not ppt_id:
        missing = []
        if not pdf_id: missing.append("PDF Report")
        if not ppt_id: missing.append("PPT/Google Slide Presentation")
        raise HTTPException(
            status_code=400,
            detail=f"Missing files in Workspace: Could not find the latest {' and '.join(missing)}."
        )

    luigi_payload = {
        "secret_key": LUIGI_MIDDLEWARE_KEY_NAME,
        "action": "SEND_EMAIL",
        "to": payload.to,
        "cc": payload.cc,
        "subject": payload.subject,
        "htmlBody": payload.body,
        "attachmentIds": [pdf_id, ppt_id]
    }

    response = requests.post(WEB_APP_URL, json=luigi_payload)

    # Catch Apps Script silent JSON errors
    luigi_result = response.json()
    if luigi_result.get("success") is False:
        error_msg = luigi_result.get("error", "Unknown Apps Script error")
        raise HTTPException(status_code=400, detail=f"Luigi failed: {error_msg}")

    response.raise_for_status()

    # Mark the Final Milestone as complete!
    cursor.execute("""
        INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
        VALUES (gen_random_uuid(), %s, 'Final Email Sent', true)
        ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true
    """, (test_id,))
    cursor.connection.commit()

    return {"status": "Success"}


# request meeting
@router.get("/{test_id}/meeting-participants")
def get_meeting_participants(test_id: str, current_user: dict = Depends(get_current_user),
                             cursor=Depends(get_db_cursor)):
    """
    Endpoint to Get Meeting Participants
    """
    # Get Pentesters
    cursor.execute("SELECT u.email FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = %s",
                   (test_id,))
    emails = [r[0] for r in cursor.fetchall() if r[0]]

    # Get Asset Contacts
    cursor.execute("""
        SELECT DISTINCT c.email FROM test_assets ta 
        JOIN assets a ON ta.asset_id = a.id 
        JOIN raw_asset_contacts rac ON a.raw_asset_id = rac.raw_asset_id
        JOIN contacts c ON rac.contact_id = c.id WHERE ta.test_id = %s
    """, (test_id,))
    emails.extend([r[0] for r in cursor.fetchall() if r[0]])

    # Get Country Contacts
    cursor.execute("""
        SELECT DISTINCT con.email
        FROM test_assets ta
        JOIN assets a ON ta.asset_id = a.id
        JOIN country_contacts cc ON a.country_id = cc.country_id
        JOIN contacts con ON cc.contact_id = con.id
        WHERE ta.test_id = %s
    """, (test_id,))
    emails.extend([r[0] for r in cursor.fetchall() if r[0]])

    emails = list(set([e for e in emails if e]))  # Deduplicate
    return {"emails": emails}


# ==========================================
# --- 3. MEETING SCHEDULING ENDPOINTS ---
# ==========================================
@router.post("/{test_id}/request-meeting-proposals")
def request_meeting_proposals(test_id: str, payload: MeetingProposalRequest,
                              current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Endpoint to Request Meeting Proposals to Luigi
    Use the emails sent from the React modal!
    1. Fetch test dates, duration, and test name
    2. Calculate the Strict Time Boundaries
    3. Ask Apps Script for the Calendars using the strict boundaries
    4. Drop the data into Pub/Sub for the Luigi Worker
    """
    meeting_type = payload.meeting_type
    emails = payload.emails  # Use the emails sent from the React modal!

    # 1. Fetch test dates, duration, and test name
    cursor.execute("""
            SELECT t.start_week, t.start_year, t.duration_weeks, t.name, c.name 
            FROM tests t 
            LEFT JOIN test_assets ta ON t.id = ta.test_id
            LEFT JOIN assets a ON ta.asset_id = a.id
            LEFT JOIN countries c ON a.country_id = c.id
            WHERE t.id = %s LIMIT 1
        """, (test_id,))
    t_week, t_year, t_duration, test_name, country_name = cursor.fetchone()

    duration_weeks = float(t_duration) if t_duration else 1.0

    # 2. Calculate the Strict Time Boundaries
    now = datetime.now(timezone.utc)
    try:
        start_date = datetime.strptime(f'{t_year} {t_week} 1', "%G %V %u").replace(tzinfo=timezone.utc)
    except:
        start_date = now + timedelta(weeks=4)

    if "Intake" in meeting_type:
        time_min = max(now, start_date - timedelta(weeks=6))
        time_max = start_date
        if now > start_date:
            time_min = now
            time_max = now + timedelta(weeks=2)
    elif "Restitution" in meeting_type:
        end_date = start_date + timedelta(weeks=duration_weeks)
        time_min = max(now, end_date)
        time_max = time_min + timedelta(weeks=3)
    else:
        time_min = now
        time_max = now + timedelta(weeks=4)

    # 3. Ask Apps Script for the Calendars using the strict boundaries
    luigi_payload = {
        "secret_key": LUIGI_MIDDLEWARE_KEY_NAME,
        "action": "GET_FREEBUSY",
        "emails": emails,
        "timeMin": time_min.isoformat(),
        "timeMax": time_max.isoformat()
    }

    response = requests.post(WEB_APP_URL, json=luigi_payload)
    free_busy_data = response.json()

    # 4. Drop the data into Pub/Sub for the Luigi Worker
    publisher = pubsub_v1.PublisherClient()
    message_data = {
        "task": "SCHEDULE_MEETING",
        "test_id": test_id,
        "test_name": test_name,
        "country_name": country_name or "Unknown Location",
        "meeting_type": meeting_type,
        "user_email": current_user["email"],
        "free_busy": free_busy_data,
        "emails": emails
    }

    publisher.publish(PUBSUB_TOPIC_PATH, json.dumps(message_data).encode("utf-8"))
    return {"message": "Luigi is analyzing the calendars. You will be notified shortly!"}


# Luigi  will call this when it's done thinking!
@router.post("/save-meeting-proposals")
async def receive_meeting_proposals(payload: dict, token: str = Depends(verify_luigi_token)):
    """
    Luigi  will call this when it's done thinking!

    Payload contains the test_id, user_email, and the AI's proposed slots.
    """
    # payload contains the test_id, user_email, and the AI's proposed slots
    user_email = payload.get("user_email")

    # Broadcast directly to the user's browser!
    await manager.broadcast(json.dumps({
        "action": "MEETING_PROPOSALS_READY",
        "email": user_email,
        "test_id": payload.get("test_id"),
        "test_name": payload.get("test_name"),
        "meeting_type": payload.get("meeting_type"),
        "proposals": payload.get("proposals"),
        "emails": payload.get("emails")
    }))

    return {"status": "success"}


# schedule meeting
@router.post("/{test_id}/book-meeting")
def book_meeting(test_id: str, payload: dict, current_user: dict = Depends(get_current_user),
                 cursor=Depends(get_db_cursor)):
    """
    Endpoint to book a meeting
    """
    # Payload expects: summary, description, emails, startTime, endTime, meeting_type
    luigi_payload = {
        "secret_key": LUIGI_MIDDLEWARE_KEY_NAME,
        "action": "SCHEDULE_MEETING",
        "summary": payload.get("summary"),
        "description": payload.get("description", ""),
        "emails": payload.get("emails", []),
        "startTime": payload.get("startTime"),
        "endTime": payload.get("endTime")
    }

    response = requests.post(WEB_APP_URL, json=luigi_payload)
    luigi_result = response.json()

    if luigi_result.get("success") is False:
        raise HTTPException(status_code=400, detail=f"Booking failed: {luigi_result.get('error')}")

    # Mark the specific Milestone as complete!
    meeting_type = payload.get("meeting_type")  # e.g., 'Intake Meeting Planned'
    if meeting_type:
        cursor.execute("""
            INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
            VALUES (gen_random_uuid(), %s, %s, true)
            ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true
        """, (test_id, meeting_type))
        cursor.connection.commit()

    return {"status": "Success", "link": luigi_result.get("data", {}).get("eventLink")}


# ==========================================
# --- 4. VULNERABILITY DRAFTING ---
# ==========================================
@router.post("/draft-vulnerability", status_code=status.HTTP_200_OK)
def trigger_luigi_draft(payload: dict, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    test_id = payload.get("test_id")
    requires_mitre = False

    # 1. Query the database to see if this test's service lane requires MITRE mapping
    if test_id:
        cursor.execute("""
                SELECT sl.requires_mitre 
                FROM tests t 
                JOIN services_lanes sl ON t.service_lane_id = sl.id 
                WHERE t.id = %s
            """, (test_id,))
        row = cursor.fetchone()
        if row:
            requires_mitre = row[0]

    publisher = pubsub_v1.PublisherClient()

    message_data = {
        "task": "DRAFT_VULNERABILITY",
        "note": payload.get("note"),
        "severity": payload.get("severity"),
        "user_email": current_user["email"],
        "requires_mitre": requires_mitre
    }

    data = json.dumps(message_data).encode("utf-8")
    publisher.publish(PUBSUB_TOPIC_PATH, data)

    return {"message": "Task dispatched to Luigi."}


#  Webhook Callback (Called by Luigi)
@router.post("/vuln-draft-callback")
def luigi_draft_callback(payload: dict, background_tasks: BackgroundTasks, token: str = Depends(verify_luigi_token)):
    """
    Webhook Callback (Called by Luigi)

    Luigi hits this endpoint when the drafted HTML is ready.
    """
    ws_message = {
        "action": "VULN_DRAFT_READY",
        "email": payload.get("user_email"),
        "html": payload.get("html"),
        "suggested_type": payload.get("suggested_type"),
        "mitre_id": payload.get("mitre_id", "")
    }

    # Broadcast to the user waiting in the frontend
    background_tasks.add_task(manager.broadcast, json.dumps(ws_message))
    return {"status": "success"}


# ==========================================
# --- 5. VALIDATION QUEUE ---
# ==========================================
@router.post("/validation-callback", summary="Webhook for Luigi's Validation Verdict")
async def luigi_validation_callback(
        payload: dict,
        background_tasks: BackgroundTasks,
        cursor=Depends(get_db_cursor),
        token: str = Depends(verify_luigi_token)
):
    vuln_uuid = payload.get("vuln_uuid")
    ai_suggestion = payload.get("ai_suggestion")
    gcs_uris = payload.get("gcs_uris", [])

    if not vuln_uuid or not ai_suggestion:
        return {"status": "Error", "message": "Missing required fields"}

    # 1. Save Luigi's verdict to the DB
    cursor.execute("""
        UPDATE kiss24_validating_vulns 
        SET ai_suggestion = %s, updated_at = NOW(), updated_by_name = 'Luigi (AI)'
        WHERE uuid = %s
    """, (ai_suggestion, vuln_uuid))
    cursor.connection.commit()

    # 2. Cleanup evidence files securely in the background
    background_tasks.add_task(cleanup_temp_evidence, gcs_uris)

    # 3. Broadcast to the frontend to STOP the spinning wand and show the result!
    await manager.broadcast(json.dumps({"action": "REFRESH_BOARD"}))

    return {"status": "Success"}