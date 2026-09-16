import os
import json
import requests
from datetime import datetime, timedelta, timezone
from google.cloud import pubsub_v1, storage
from fastapi import HTTPException
from utils.secret_manager import get_secret

WEB_APP_URL = os.environ.get("LUIGI_MIDDLEWARE_CONTACTS_URL")
LUIGI_MIDDLEWARE_KEY_NAME = get_secret(os.environ.get("LUIGI_MIDDLEWARE_KEY_NAME"))
PUBSUB_TOPIC_PATH = os.environ.get("PUBSUB_TOPIC_PATH")


def cleanup_temp_evidence(uris: list):
    if not uris: return
    try:
        storage_client = storage.Client()
        for uri in uris:
            parts = uri.replace("gs://", "").split("/", 1)
            if len(parts) == 2:
                bucket = storage_client.bucket(parts[0])
                blob = bucket.blob(parts[1])
                if blob.exists():
                    blob.delete()
    except Exception as e:
        print(f"Failed to clean up temp bucket: {e}")

def check_maintainer_lane_access(current_user: dict, target_lane_id: str):
    if current_user.get('role') == 'maintainer':
        if str(current_user.get('service_lane_id')) != str(target_lane_id):
            raise HTTPException(status_code=403, detail="Maintainers can only perform actions on tests in their assigned Service Lane.")



# --- INTRO EMAIL ---
def draft_intro_email(cursor, test_id: str, current_user: dict):
    cursor.execute("""
        SELECT t.name, t.start_week, t.start_year, t.service_lane_id, a.name as asset_name, c.code as country_code, s.name as service_name, s.intro_email_template, s.auto_provision_workspace
        FROM tests t
        LEFT JOIN services_lanes s ON t.service_lane_id = s.id
        LEFT JOIN test_assets ta ON t.id = ta.test_id
        LEFT JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN countries c ON a.country_id = c.id
        WHERE t.id = %s LIMIT 1
    """, (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found")

    t_name, t_week, t_year, t_lane_id, asset_name, country_code, service_name, db_template, auto_provision = row
    check_maintainer_lane_access(current_user, t_lane_id)

    if not db_template:
        raise HTTPException(status_code=400, detail=f"No Intro Email Template configured for '{service_name}'.")

    cursor.execute("SELECT DISTINCT u.name, u.email FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = %s", (test_id,))
    pentester_rows = cursor.fetchall()
    pentesters = ", ".join([r[0] for r in pentester_rows if r[0]])
    pentester_emails = set([r[1] for r in pentester_rows if r[1]])

    start_date_str = "TBD"
    if t_year and t_week:
        try:
            start_date_str = datetime.strptime(f'{t_year} {t_week} 1', "%G %V %u").strftime("%B %d, %Y")
        except: pass

    cursor.execute("""
        SELECT c.email, cc.is_developer, cc.is_stakeholder FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN country_contacts cc ON a.country_id = cc.country_id JOIN contacts c ON cc.contact_id = c.id WHERE ta.test_id = %s
        UNION
        SELECT c.email, rac.is_developer, rac.is_stakeholder FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN raw_asset_contacts rac ON a.raw_asset_id = rac.raw_asset_id JOIN contacts c ON rac.contact_id = c.id WHERE ta.test_id = %s
    """, (test_id, test_id))

    dev_emails, stakeholder_emails = set(), set()
    for email, is_dev, is_stake in cursor.fetchall():
        if email:
            if is_dev: dev_emails.add(email)
            if is_stake: stakeholder_emails.add(email)

    to_list = list(dev_emails)
    cc_list = list(stakeholder_emails) + list(pentester_emails)

    if not to_list:
        to_list = list(stakeholder_emails)
        cc_list = list(pentester_emails)
    if not to_list:
        to_list = list(pentester_emails)
        cc_list = []

    cc_list = list(set(cc_list) - set(to_list))

    body = db_template.replace("{{service_lane}}", service_name or "Service").replace("{{country_code}}", country_code or "Country").replace("{{asset_name}}", asset_name or "Asset").replace("{{week}}", str(t_week) or "TBD").replace("{{year}}", str(t_year) or "TBD").replace("{{week_start_date}}", start_date_str).replace("{{pentesters}}", pentesters or "TBD")
    return {"to": ", ".join(to_list), "cc": ", ".join(cc_list), "subject": f"Security Pentest Setup: {country_code or ''} - {asset_name or ''} (Week {t_week or ''})", "body": body}


def send_intro_email(cursor, test_id: str, payload, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, row[0])

    if not payload.to and not payload.cc: raise HTTPException(status_code=400, detail="At least one recipient (To or CC) is required.")

    all_recipients = payload.to + (f",{payload.cc}" if payload.cc else "")
    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "SEND_EMAIL", "to": all_recipients, "subject": payload.subject, "htmlBody": payload.body}

    response = requests.post(WEB_APP_URL, json=luigi_payload)
    response.raise_for_status()
    if response.json().get("success") is False:
        raise HTTPException(status_code=400, detail=f"Luigi failed: {response.json().get('error', 'Unknown error')}")

    cursor.execute("INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, 'Information Email Sent', true) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true", (test_id,))
    cursor.connection.commit()
    return {"status": "Success"}


# --- FINAL EMAIL ---
def draft_final_email(cursor, test_id: str, current_user: dict):
    cursor.execute("""
        SELECT t.name, t.start_week, t.start_year, t.kiss24, t.service_lane_id, a.name as asset_name, c.code as country_code, s.name as service_name, s.final_email_template
        FROM tests t LEFT JOIN services_lanes s ON t.service_lane_id = s.id LEFT JOIN test_assets ta ON t.id = ta.test_id LEFT JOIN assets a ON ta.asset_id = a.id LEFT JOIN countries c ON a.country_id = c.id
        WHERE t.id = %s LIMIT 1
    """, (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found")

    t_name, t_week, t_year, kiss24, t_lane_id, asset_name, country_code, service_name, db_template = row
    check_maintainer_lane_access(current_user, t_lane_id)

    if not db_template: raise HTTPException(status_code=400, detail=f"No Final Email Template configured for '{service_name}'.")

    cursor.execute("SELECT DISTINCT u.name, u.email FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = %s", (test_id,))
    pentester_rows = cursor.fetchall()
    pentesters = ", ".join([r[0] for r in pentester_rows if r[0]])
    pentester_emails = set([r[1] for r in pentester_rows if r[1]])

    cursor.execute("""
        SELECT c.email, cc.is_developer, cc.is_stakeholder FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN country_contacts cc ON a.country_id = cc.country_id JOIN contacts c ON cc.contact_id = c.id WHERE ta.test_id = %s
        UNION
        SELECT c.email, rac.is_developer, rac.is_stakeholder FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN raw_asset_contacts rac ON a.raw_asset_id = rac.raw_asset_id JOIN contacts c ON rac.contact_id = c.id WHERE ta.test_id = %s
    """, (test_id, test_id))

    dev_emails, stakeholder_emails = set(), set()
    for email, is_dev, is_stake in cursor.fetchall():
        if email:
            if is_dev: dev_emails.add(email)
            if is_stake: stakeholder_emails.add(email)

    to_list = list(dev_emails)
    cc_list = list(stakeholder_emails) + list(pentester_emails)

    if not to_list:
        to_list = list(stakeholder_emails)
        cc_list = list(pentester_emails)
    if not to_list:
        to_list = list(pentester_emails)
        cc_list = []

    cc_list = list(set(cc_list) - set(to_list))

    body = db_template.replace("{{service_lane}}", service_name or "Service").replace("{{country_code}}", country_code or "Country").replace("{{asset_name}}", asset_name or "Asset").replace("{{week}}", str(t_week) or "TBD").replace("{{year}}", str(t_year) or "TBD").replace("{{pentesters}}", pentesters or "TBD").replace("{{kiss24}}", str(kiss24) if kiss24 else "MISSING_KISS24_ID")
    return {"to": ", ".join(to_list), "cc": ", ".join(cc_list), "subject": f"Pentest Completed: {country_code or ''} - {asset_name or ''} ({service_name or ''})", "body": body}


def send_final_email(cursor, test_id: str, payload, current_user: dict):
    cursor.execute("SELECT drive_folder_id, service_lane_id FROM tests WHERE id = %s", (test_id,))
    folder_row = cursor.fetchone()
    if not folder_row: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, folder_row[1])

    if not payload.to and not payload.cc: raise HTTPException(status_code=400, detail="At least one recipient required.")
    if not folder_row[0]: raise HTTPException(status_code=400, detail="No Google Drive Workspace found for this test.")

    cursor.execute("SELECT drive_file_id, file_name, mime_type FROM test_documents WHERE test_id = %s ORDER BY last_modified DESC", (test_id,))
    documents = cursor.fetchall()
    pdf_id, ppt_id = None, None

    for doc_id, file_name, mime_type in documents:
        name_lower = file_name.lower()
        if not pdf_id and (mime_type == 'application/pdf' or name_lower.endswith('.pdf')): pdf_id = doc_id
        if not ppt_id and (mime_type in ['application/vnd.google-apps.presentation', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'application/vnd.ms-powerpoint'] or name_lower.endswith(('.ppt', '.pptx'))): ppt_id = doc_id

    if not pdf_id or not ppt_id: raise HTTPException(status_code=400, detail=f"Missing files in Workspace.")

    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "SEND_EMAIL", "to": payload.to, "cc": payload.cc, "subject": payload.subject, "htmlBody": payload.body, "attachmentIds": [pdf_id, ppt_id]}

    response = requests.post(WEB_APP_URL, json=luigi_payload)
    response.raise_for_status()
    if response.json().get("success") is False: raise HTTPException(status_code=400, detail=f"Luigi failed: {response.json().get('error')}")

    cursor.execute("INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, 'Final Email Sent', true) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true", (test_id,))
    cursor.connection.commit()
    return {"status": "Success"}


# --- MEETINGS ---
def get_meeting_participants(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, row[0])

    emails = []
    cursor.execute("SELECT u.email FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = %s", (test_id,))
    emails.extend([r[0] for r in cursor.fetchall() if r[0]])

    cursor.execute("SELECT DISTINCT c.email FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN raw_asset_contacts rac ON a.raw_asset_id = rac.raw_asset_id JOIN contacts c ON rac.contact_id = c.id WHERE ta.test_id = %s", (test_id,))
    emails.extend([r[0] for r in cursor.fetchall() if r[0]])

    cursor.execute("SELECT DISTINCT con.email FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN country_contacts cc ON a.country_id = cc.country_id JOIN contacts con ON cc.contact_id = con.id WHERE ta.test_id = %s", (test_id,))
    emails.extend([r[0] for r in cursor.fetchall() if r[0]])

    return {"emails": list(set([e for e in emails if e]))}


def request_meeting_proposals(cursor, test_id: str, payload, current_user: dict):
    cursor.execute("""
        SELECT t.start_week, t.start_year, t.duration_weeks, t.name, c.name, t.service_lane_id 
        FROM tests t LEFT JOIN test_assets ta ON t.id = ta.test_id LEFT JOIN assets a ON ta.asset_id = a.id LEFT JOIN countries c ON a.country_id = c.id
        WHERE t.id = %s LIMIT 1
    """, (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")

    t_week, t_year, t_duration, test_name, country_name, t_lane_id = row
    check_maintainer_lane_access(current_user, t_lane_id)

    duration_weeks = float(t_duration) if t_duration else 1.0
    now = datetime.now(timezone.utc)
    try: start_date = datetime.strptime(f'{t_year} {t_week} 1', "%G %V %u").replace(tzinfo=timezone.utc)
    except: start_date = now + timedelta(weeks=4)

    if "Intake" in payload.meeting_type:
        time_min, time_max = max(now, start_date - timedelta(weeks=6)), start_date
        if now > start_date: time_min, time_max = now, now + timedelta(weeks=2)
    elif "Restitution" in payload.meeting_type:
        end_date = start_date + timedelta(weeks=duration_weeks)
        time_min, time_max = max(now, end_date), max(now, end_date) + timedelta(weeks=3)
    else:
        time_min, time_max = now, now + timedelta(weeks=4)

    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "GET_FREEBUSY", "emails": payload.emails, "timeMin": time_min.isoformat(), "timeMax": time_max.isoformat()}
    response = requests.post(WEB_APP_URL, json=luigi_payload)

    pubsub_v1.PublisherClient().publish(PUBSUB_TOPIC_PATH, json.dumps({
        "task": "SCHEDULE_MEETING", "test_id": test_id, "test_name": test_name, "country_name": country_name or "Unknown Location",
        "meeting_type": payload.meeting_type, "user_email": current_user["email"], "free_busy": response.json(), "emails": payload.emails
    }).encode("utf-8"))
    return {"message": "Luigi is analyzing the calendars. You will be notified shortly!"}


def book_meeting(cursor, test_id: str, payload: dict, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, row[0])

    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "SCHEDULE_MEETING", "summary": payload.get("summary"), "description": payload.get("description", ""), "emails": payload.get("emails", []), "startTime": payload.get("startTime"), "endTime": payload.get("endTime")}
    response = requests.post(WEB_APP_URL, json=luigi_payload)
    luigi_result = response.json()

    if luigi_result.get("success") is False: raise HTTPException(status_code=400, detail=f"Booking failed: {luigi_result.get('error')}")

    if meeting_type := payload.get("meeting_type"):
        cursor.execute("INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, %s, true) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true", (test_id, meeting_type))
        cursor.connection.commit()
    return {"status": "Success", "link": luigi_result.get("data", {}).get("eventLink")}


# --- VULNERABILITIES & VALIDATION ---
def trigger_luigi_draft(cursor, payload: dict, current_user: dict):
    test_id = payload.get("test_id")
    requires_mitre = False
    if test_id:
        cursor.execute("SELECT sl.requires_mitre, sl.id FROM tests t JOIN services_lanes sl ON t.service_lane_id = sl.id WHERE t.id = %s", (test_id,))
        row = cursor.fetchone()
        if not row: raise HTTPException(status_code=404, detail="Test not found.")
        requires_mitre, t_lane_id = row
        check_maintainer_lane_access(current_user, t_lane_id)

    pubsub_v1.PublisherClient().publish(PUBSUB_TOPIC_PATH, json.dumps({"task": "DRAFT_VULNERABILITY", "note": payload.get("note"), "severity": payload.get("severity"), "user_email": current_user["email"], "requires_mitre": requires_mitre}).encode("utf-8"))
    return {"message": "Task dispatched to Luigi."}


def process_validation_callback(cursor, payload: dict):
    vuln_uuid = payload.get("vuln_uuid")
    ai_suggestion = payload.get("ai_suggestion")
    gcs_uris = payload.get("gcs_uris", [])

    if not vuln_uuid or not ai_suggestion: return {"status": "Error", "message": "Missing required fields"}, []

    cursor.execute("UPDATE kiss24_validating_vulns SET ai_suggestion = %s, updated_at = NOW(), updated_by_name = 'Luigi (AI)' WHERE uuid = %s", (ai_suggestion, vuln_uuid))
    cursor.connection.commit()
    return {"status": "Success"}, gcs_uris