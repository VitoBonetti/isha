import google.auth
from google.auth.transport.requests import Request
import requests
import os
from fastapi import APIRouter, Depends, HTTPException
from utils.secret_manager import get_secret
from schema import SendEmailPayload
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin, require_write_access
from audit_logger import log_audit_event
from datetime import datetime


router = APIRouter(prefix="/api/luigi", tags=["Luigi"])

WEB_APP_URL = os.environ.get("LUIGI_MIDDLEWARE_CONTACTS_URL")
LUIGI_MIDDLEWARE_KEY_NAME = get_secret(os.environ.get("LUIGI_MIDDLEWARE_KEY_NAME"))

DEFAULT_INTRO_TEMPLATE = """
<div>Hi All,</div>
<div>We are finalizing the <strong>{{service_lane}}</strong> penetration test schedule for <strong>{{country_code}} - {{asset_name}}</strong>.</div>
<div><strong>Schedule:</strong> Week {{week}}, {{year}} (Starting {{week_start_date}})<br/>
<strong>Assigned Pentesters:</strong> {{pentesters}}</div>

<h3>{{service_lane}} Setup Requirements</h3>
<div>To ensure the test starts on time, could you please ensure the following access and environments are ready prior to the start date?</div>
<ul>
  <li><strong>Source Code Access:</strong> If the code is hosted on Corporate GitLab, please add the Global Offensive Security Team (Group ID: 252) as a Reporter.</li>
  <li><strong>Infrastructure Access:</strong> Read-only access to the relevant infrastructure.</li>
  <li><strong>Environment:</strong> Access to a stable UAT environment that is available 24/7.</li>
  <li><strong>Documentation:</strong> Links to any relevant architectural or API documentation.</li>
  <li><strong>Test Accounts:</strong> Credentials for test accounts covering every key role.</li>
  <li><strong>Connectivity:</strong> VPN access (if required to access the environment).</li>
  <li><strong>Mobile:</strong> If this is a mobile Application, or it has a mobile version, please share the latest APK and IPA files. We will need two versions of each: a standard build with all security protections enabled (SSL pinning and root detection ON), and an unprotected build where these protections are disabled.</li>
</ul>

<h3>Intake Meeting</h3>
<div>We need to set up a brief intake meeting before we begin. The goals of this call are to explain the pentesting process to the dev team, allow the testers to gain a functional understanding of the application, and verify accessibility.</div>
<div>We will follow up later this week with a calendar invitation for this meeting.</div>
<div>If you have any questions in the meantime, please feel free to reach out.</div>

<p style="color: #666; font-size: 12px; margin-top: 30px;"><em>This is an automated message from the Global Offensive Security Team.</em></div>
"""


# Intro email
@router.get("/{test_id}/draft-intro-email")
def draft_intro_email(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # 1. Fetch Test, Asset, Country, and Service data using the correct junction tables
    cursor.execute("""
        SELECT t.name, t.start_week, t.start_year,
               a.name as asset_name, 
               c.code as country_code, 
               s.name as service_name, s.intro_email_template
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

    t_name, t_week, t_year, asset_name, country_code, service_name, db_template = row

    # 2. Fetch Pentesters using the correct Assignments table
    cursor.execute("""
            SELECT DISTINCT u.name, u.email 
            FROM assignments a
            JOIN users u ON a.user_id = u.id
            WHERE a.test_id = %s
        """, (test_id,))
    pentester_rows = cursor.fetchall()

    # Extract names for the email body template
    pentesters = ", ".join([r[0] for r in pentester_rows if r[0]])
    # Extract emails to add to the CC list
    pentester_emails = [r[1] for r in pentester_rows if r[1]]

    # 3. Calculate the start date (Monday of the given week/year)
    start_date_str = "TBD"
    if t_year and t_week:
        try:
            start_date = datetime.strptime(f'{t_year} {t_week} 1', "%G %V %u")
            start_date_str = start_date.strftime("%B %d, %Y")
        except:
            pass

    # 4. Fetch the REAL Contacts! (Using the CountryContacts junction)
    cursor.execute("""
        SELECT DISTINCT con.email
        FROM test_assets ta
        JOIN assets a ON ta.asset_id = a.id
        JOIN country_contacts cc ON a.country_id = cc.country_id
        JOIN contacts con ON cc.contact_id = con.id
        WHERE ta.test_id = %s
    """, (test_id,))
    contact_emails = [r[0] for r in cursor.fetchall() if r[0]]

    # Leave blank for now to prevent crashes; admin will fill in UI
    to_email = contact_emails[0] if len(contact_emails) > 0 else ""
    cc_list = contact_emails[1:] if len(contact_emails) > 1 else []
    cc_list.extend(pentester_emails)
    cc_list = list(set([e for e in cc_list if e]))
    cc_emails = ", ".join(cc_list)

    # 4. Populate Template
    template = db_template if db_template else DEFAULT_INTRO_TEMPLATE
    body = template.replace("{{service_lane}}", service_name or "Service")
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


@router.post("/{test_id}/send-intro-email")
def send_intro_email(test_id: str, payload: SendEmailPayload, current_user: dict = Depends(get_current_user),
                     cursor=Depends(get_db_cursor)):

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
