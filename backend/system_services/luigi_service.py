import os
import json
import uuid
import requests
from datetime import datetime, timedelta, timezone
from google.cloud import pubsub_v1, storage
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from models.tests import Tests, TestAssets, TestMilestone, TestDocuments, Assignments
from models.services import ServiceLanes
from models.assets import Assets
from models.raw_assets import RawAssets
from models.territories import Country
from models.users import Users
from models.contacts import Contacts, CountryContacts, RawAssetContacts
from models.kiss24 import Kiss24ValidatingVulns
from utils.secret_manager import get_secret
from utils.timeaware import aware_utcnow

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
            raise HTTPException(status_code=403,
                                detail="Maintainers can only perform actions on tests in their assigned Service Lane.")


def _get_test_emails(db: Session, test_id: str):
    """Helper to fetch all emails associated with a test."""
    pentesters = (db.query(Users.name, Users.email)
                  .join(Assignments, Users.id == Assignments.user_id)
                  .filter(Assignments.test_id == test_id).distinct().all())

    country_contacts = (db.query(Contacts.email, CountryContacts.is_developer, CountryContacts.is_stakeholder)
                        .join(CountryContacts, Contacts.id == CountryContacts.contact_id)
                        .join(Assets, CountryContacts.country_id == Assets.country_id)
                        .join(TestAssets, Assets.id == TestAssets.asset_id)
                        .filter(TestAssets.test_id == test_id).all())

    asset_contacts = (db.query(Contacts.email, RawAssetContacts.is_developer, RawAssetContacts.is_stakeholder)
                      .join(RawAssetContacts, Contacts.id == RawAssetContacts.contact_id)
                      .join(Assets, RawAssetContacts.raw_asset_id == Assets.raw_asset_id)
                      .join(TestAssets, Assets.id == TestAssets.asset_id)
                      .filter(TestAssets.test_id == test_id).all())

    return pentesters, country_contacts + asset_contacts


def _upsert_test_milestone(db: Session, test_id: str, step_name: str):
    """Helper to upsert a test milestone."""
    stmt = insert(TestMilestone).values(
        id=str(uuid.uuid4()),
        test_id=test_id,
        step_name=step_name,
        is_completed=True
    ).on_conflict_do_update(
        index_elements=['test_id', 'step_name'],
        set_={'is_completed': True}
    )
    db.execute(stmt)
    db.commit()


# --- INTRO EMAIL ---
def draft_intro_email(db: Session, test_id: str, current_user: dict):
    test_data = (db.query(
        Tests.name, Tests.start_week, Tests.start_year, Tests.service_lane_id,
        Assets.name.label("asset_name"), Country.code.label("country_code"),
        ServiceLanes.name.label("service_name"), ServiceLanes.intro_email_template)
                 .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                 .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
                 .outerjoin(Assets, TestAssets.asset_id == Assets.id)
                 .outerjoin(Country, Assets.country_id == Country.id)
                 .filter(Tests.id == test_id).first())

    if not test_data: raise HTTPException(status_code=404, detail="Test not found")
    check_maintainer_lane_access(current_user, str(test_data.service_lane_id))

    if not test_data.intro_email_template:
        raise HTTPException(status_code=400,
                            detail=f"No Intro Email Template configured for '{test_data.service_name}'.")

    pentesters, contacts = _get_test_emails(db, test_id)

    pentester_names = ", ".join([p.name for p in pentesters if p.name])
    pentester_emails = {p.email for p in pentesters if p.email}

    start_date_str = "TBD"
    if test_data.start_year and test_data.start_week:
        try:
            start_date_str = datetime.strptime(f'{test_data.start_year} {test_data.start_week} 1', "%G %V %u").strftime(
                "%B %d, %Y")
        except:
            pass

    dev_emails, stakeholder_emails = set(), set()
    for email, is_dev, is_stake in contacts:
        if email:
            if is_dev: dev_emails.add(email)
            if is_stake: stakeholder_emails.add(email)

    to_list = list(dev_emails)
    cc_list = list(stakeholder_emails) + list(pentester_emails)

    if not to_list:
        to_list, cc_list = list(stakeholder_emails), list(pentester_emails)
    if not to_list:
        to_list, cc_list = list(pentester_emails), []

    cc_list = list(set(cc_list) - set(to_list))

    body = (test_data.intro_email_template
            .replace("{{service_lane}}", test_data.service_name or "Service")
            .replace("{{country_code}}", test_data.country_code or "Country")
            .replace("{{asset_name}}", test_data.asset_name or "Asset")
            .replace("{{week}}", str(test_data.start_week) or "TBD")
            .replace("{{year}}", str(test_data.start_year) or "TBD")
            .replace("{{week_start_date}}", start_date_str)
            .replace("{{pentesters}}", pentester_names or "TBD"))

    return {"to": ", ".join(to_list), "cc": ", ".join(cc_list),
            "subject": f"Security Pentest Setup: {test_data.country_code or ''} - {test_data.asset_name or ''} (Week {test_data.start_week or ''})",
            "body": body}


def send_intro_email(db: Session, test_id: str, payload, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, str(test.service_lane_id))

    if not payload.to and not payload.cc:
        raise HTTPException(status_code=400, detail="At least one recipient (To or CC) is required.")

    all_recipients = payload.to + (f",{payload.cc}" if payload.cc else "")
    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "SEND_EMAIL", "to": all_recipients,
                     "subject": payload.subject, "htmlBody": payload.body}

    response = requests.post(WEB_APP_URL, json=luigi_payload)
    response.raise_for_status()
    if response.json().get("success") is False:
        raise HTTPException(status_code=400, detail=f"Luigi failed: {response.json().get('error', 'Unknown error')}")

    _upsert_test_milestone(db, test_id, 'Information Email Sent')
    return {"status": "Success"}


# --- FINAL EMAIL ---
def draft_final_email(db: Session, test_id: str, current_user: dict):
    test_data = (db.query(
        Tests.name, Tests.start_week, Tests.start_year, Tests.service_lane_id, Tests.kiss24,
        Assets.name.label("asset_name"), Country.code.label("country_code"),
        ServiceLanes.name.label("service_name"), ServiceLanes.final_email_template)
                 .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                 .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
                 .outerjoin(Assets, TestAssets.asset_id == Assets.id)
                 .outerjoin(Country, Assets.country_id == Country.id)
                 .filter(Tests.id == test_id).first())

    if not test_data: raise HTTPException(status_code=404, detail="Test not found")
    check_maintainer_lane_access(current_user, str(test_data.service_lane_id))

    if not test_data.final_email_template:
        raise HTTPException(status_code=400,
                            detail=f"No Final Email Template configured for '{test_data.service_name}'.")

    pentesters, contacts = _get_test_emails(db, test_id)

    pentester_names = ", ".join([p.name for p in pentesters if p.name])
    pentester_emails = {p.email for p in pentesters if p.email}

    dev_emails, stakeholder_emails = set(), set()
    for email, is_dev, is_stake in contacts:
        if email:
            if is_dev: dev_emails.add(email)
            if is_stake: stakeholder_emails.add(email)

    to_list = list(dev_emails)
    cc_list = list(stakeholder_emails) + list(pentester_emails)

    if not to_list:
        to_list, cc_list = list(stakeholder_emails), list(pentester_emails)
    if not to_list:
        to_list, cc_list = list(pentester_emails), []

    cc_list = list(set(cc_list) - set(to_list))

    body = (test_data.final_email_template
            .replace("{{service_lane}}", test_data.service_name or "Service")
            .replace("{{country_code}}", test_data.country_code or "Country")
            .replace("{{asset_name}}", test_data.asset_name or "Asset")
            .replace("{{week}}", str(test_data.start_week) or "TBD")
            .replace("{{year}}", str(test_data.start_year) or "TBD")
            .replace("{{pentesters}}", pentester_names or "TBD")
            .replace("{{kiss24}}", str(test_data.kiss24) if test_data.kiss24 else "MISSING_KISS24_ID"))

    return {"to": ", ".join(to_list), "cc": ", ".join(cc_list),
            "subject": f"Pentest Completed: {test_data.country_code or ''} - {test_data.asset_name or ''} ({test_data.service_name or ''})",
            "body": body}


def send_final_email(db: Session, test_id: str, payload, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, str(test.service_lane_id))

    if not payload.to and not payload.cc: raise HTTPException(status_code=400,
                                                              detail="At least one recipient required.")
    if not test.drive_folder_id: raise HTTPException(status_code=400,
                                                     detail="No Google Drive Workspace found for this test.")

    documents = db.query(TestDocuments).filter(TestDocuments.test_id == test_id).order_by(
        TestDocuments.last_modified.desc()).all()
    pdf_id, ppt_id = None, None

    for doc in documents:
        name_lower = doc.file_name.lower()
        if not pdf_id and (
                doc.mime_type == 'application/pdf' or name_lower.endswith('.pdf')): pdf_id = doc.drive_file_id
        if not ppt_id and (doc.mime_type in ['application/vnd.google-apps.presentation',
                                             'application/vnd.openxmlformats-officedocument.presentationml.presentation',
                                             'application/vnd.ms-powerpoint'] or name_lower.endswith(
            ('.ppt', '.pptx'))): ppt_id = doc.drive_file_id

    if not pdf_id or not ppt_id: raise HTTPException(status_code=400, detail=f"Missing files in Workspace.")

    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "SEND_EMAIL", "to": payload.to,
                     "cc": payload.cc, "subject": payload.subject, "htmlBody": payload.body,
                     "attachmentIds": [pdf_id, ppt_id]}

    response = requests.post(WEB_APP_URL, json=luigi_payload)
    response.raise_for_status()
    if response.json().get("success") is False: raise HTTPException(status_code=400,
                                                                    detail=f"Luigi failed: {response.json().get('error')}")

    _upsert_test_milestone(db, test_id, 'Final Email Sent')
    return {"status": "Success"}


# --- MEETINGS ---
def get_meeting_participants(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, str(test.service_lane_id))

    _, contacts = _get_test_emails(db, test_id)
    emails = {e for e, _, _ in contacts if e}

    pentesters = db.query(Users.email).join(Assignments, Users.id == Assignments.user_id).filter(
        Assignments.test_id == test_id).all()
    emails.update([p.email for p in pentesters if p.email])

    return {"emails": list(emails)}


def request_meeting_proposals(db: Session, test_id: str, payload, current_user: dict):
    test_data = (db.query(
        Tests.start_week, Tests.start_year, Tests.duration_weeks, Tests.name,
        Country.name.label("country_name"), Tests.service_lane_id)
                 .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
                 .outerjoin(Assets, TestAssets.asset_id == Assets.id)
                 .outerjoin(Country, Assets.country_id == Country.id)
                 .filter(Tests.id == test_id).first())

    if not test_data: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, str(test_data.service_lane_id))

    duration_weeks = float(test_data.duration_weeks) if test_data.duration_weeks else 1.0
    now = datetime.now(timezone.utc)

    try:
        start_date = datetime.strptime(f'{test_data.start_year} {test_data.start_week} 1', "%G %V %u").replace(
            tzinfo=timezone.utc)
    except:
        start_date = now + timedelta(weeks=4)

    if "Intake" in payload.meeting_type:
        time_min, time_max = max(now, start_date - timedelta(weeks=6)), start_date
        if now > start_date: time_min, time_max = now, now + timedelta(weeks=2)
    elif "Restitution" in payload.meeting_type:
        end_date = start_date + timedelta(weeks=duration_weeks)
        time_min, time_max = max(now, end_date), max(now, end_date) + timedelta(weeks=3)
    else:
        time_min, time_max = now, now + timedelta(weeks=4)

    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "GET_FREEBUSY", "emails": payload.emails,
                     "timeMin": time_min.isoformat(), "timeMax": time_max.isoformat()}
    response = requests.post(WEB_APP_URL, json=luigi_payload)

    pubsub_v1.PublisherClient().publish(PUBSUB_TOPIC_PATH, json.dumps({
        "task": "SCHEDULE_MEETING", "test_id": test_id, "test_name": test_data.name,
        "country_name": test_data.country_name or "Unknown Location",
        "meeting_type": payload.meeting_type, "user_email": current_user["email"], "free_busy": response.json(),
        "emails": payload.emails
    }).encode("utf-8"))
    return {"message": "Luigi is analyzing the calendars. You will be notified shortly!"}


def book_meeting(db: Session, test_id: str, payload: dict, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found.")
    check_maintainer_lane_access(current_user, str(test.service_lane_id))

    luigi_payload = {"secret_key": LUIGI_MIDDLEWARE_KEY_NAME, "action": "SCHEDULE_MEETING",
                     "summary": payload.get("summary"), "description": payload.get("description", ""),
                     "emails": payload.get("emails", []), "startTime": payload.get("startTime"),
                     "endTime": payload.get("endTime")}
    response = requests.post(WEB_APP_URL, json=luigi_payload)
    luigi_result = response.json()

    if luigi_result.get("success") is False: raise HTTPException(status_code=400,
                                                                 detail=f"Booking failed: {luigi_result.get('error')}")

    if meeting_type := payload.get("meeting_type"):
        _upsert_test_milestone(db, test_id, meeting_type)

    return {"status": "Success", "link": luigi_result.get("data", {}).get("eventLink")}


# --- VULNERABILITIES & VALIDATION ---
def trigger_luigi_draft(db: Session, payload: dict, current_user: dict):
    test_id = payload.get("test_id")
    requires_mitre = False

    if test_id:
        test_info = (db.query(ServiceLanes.requires_mitre, Tests.service_lane_id)
                     .join(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                     .filter(Tests.id == test_id).first())

        if not test_info: raise HTTPException(status_code=404, detail="Test not found.")
        requires_mitre, t_lane_id = test_info
        check_maintainer_lane_access(current_user, str(t_lane_id))

    pubsub_v1.PublisherClient().publish(PUBSUB_TOPIC_PATH, json.dumps({
        "task": "DRAFT_VULNERABILITY", "note": payload.get("note"), "severity": payload.get("severity"),
        "user_email": current_user["email"], "requires_mitre": requires_mitre
    }).encode("utf-8"))

    return {"message": "Task dispatched to Luigi."}


def process_validation_callback(db: Session, payload: dict):
    vuln_uuid = payload.get("vuln_uuid")
    ai_suggestion = payload.get("ai_suggestion")
    gcs_uris = payload.get("gcs_uris", [])

    if not vuln_uuid or not ai_suggestion:
        return {"status": "Error", "message": "Missing required fields"}, []

    vuln = db.query(Kiss24ValidatingVulns).filter(Kiss24ValidatingVulns.id == vuln_uuid).first()
    if vuln:
        vuln.ai_suggestion = ai_suggestion
        vuln.updated_at = aware_utcnow()
        vuln.updated_by_name = 'Luigi (AI)'
        db.commit()

    return {"status": "Success"}, gcs_uris