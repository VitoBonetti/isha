import os
import re
import json
import difflib
import requests
from datetime import datetime
from fastapi import HTTPException, status
from google.cloud import pubsub_v1, storage
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_
from sqlalchemy.exc import IntegrityError
from models.users import Users
from models.territories import Country
from models.raw_assets import RawAssets, RawAssetsSnowMetadata
from models.kiss24 import Kiss24ContextType, Kiss24VulnTypes, kiss24_vuln_context_association, Kiss24ValidatingVulns
from models.tests import Tests, TestAssets, TestStages
from models.services import ServiceLanes
from models.assets import Assets
from audit_logger import log_audit_event
from utils.secret_manager import get_secret
from utils.security_cipher import get_cipher
from utils.timeaware import aware_utcnow
from utils.kiss24_service import (
    map_asset_onetrust_custom_field,
    map_organizations,
    create_test,
    get_test_info,
    get_test_vulns_info,
    add_snowid_to_kiss24asset,
    sync_vuln_type_kiss24,
    map_mario_user_kiss24_uuid,
    create_vulnerability,
    upload_vulnerability_attachment,
    get_custom_fields_choice_uuid,
    fetch_validating_vulnerabilities,
    fetch_validation_info,
    get_unmapped_kiss24_assets
)

KISS_24_TEMP_BUCKET = os.environ.get("KISS_24_TEMP_BUCKET")
PUBSUB_TOPIC_PATH = os.environ.get("PUBSUB_TOPIC_PATH")
KISS_24_ENDPOINT = os.environ.get("KISS_24_ENDPOINT")
KISS_24_API_KEY_NAME = os.environ.get("KISS_24_API_KEY_NAME")


# --- HELPERS ---
def check_maintainer_lane_access(current_user: dict, target_lane_id: str):
    if current_user.get('role') == 'maintainer':
        if str(current_user.get('service_lane_id')) != str(target_lane_id):
            raise HTTPException(status_code=403,
                                detail="Maintainers can only perform actions on tests in their assigned Service Lane.")


def get_user_kiss24_key(db: Session, user_id: str) -> str:
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user or not user.kiss24_api_key:
        raise HTTPException(status_code=400, detail="Configure your personal Keep Secure 24 API key first.")

    cipher = get_cipher()
    try:
        return cipher.decrypt(user.kiss24_api_key.encode('utf-8')).decode('utf-8')
    except Exception:
        raise HTTPException(status_code=400,
                            detail="Failed to decrypt your personal API key. Please reset it in your profile.")


def normalize_asset_name(name: str) -> str:
    if not name: return ""
    s = str(name).lower()
    s = re.sub(r'https?://(?:www\.)?', '', s)
    s = re.sub(r'\.(com|nl|org|net|eu).*', '', s)
    s = re.sub(r'[^\w\s]', ' ', s)
    noise_words = ['prod', 'production', 'stg', 'staging', 'dev', 'test', 'uat', 'portal', 'app', 'application']
    words = [w for w in s.split() if w not in noise_words]
    return ' '.join(words).strip()


def calculate_similarity(a: str, b: str) -> int:
    norm_a = normalize_asset_name(a) or str(a).lower()
    norm_b = normalize_asset_name(b) or str(b).lower()
    ratio = difflib.SequenceMatcher(None, norm_a, norm_b).ratio()
    return int(ratio * 100)


# --- SYNC ENDPOINTS ---
def sync_kiss24_org_ids(db: Session, current_user: dict):
    try:
        orgs_map = map_organizations()
        if not orgs_map:
            return {"status": "Success", "message": "No Organization mappings found in KISS24.",
                    "total_kiss24_mapped": 0, "total_countries_updated": 0}

        countries = db.query(Country).filter(Country.code.isnot(None)).all()
        matched_count, updated_countries = 0, []

        for country in countries:
            clean_code = str(country.code).strip()
            if clean_code in orgs_map:
                kiss24_uuid = orgs_map[clean_code]
                country.kiss24_uuid = kiss24_uuid
                matched_count += 1
                updated_countries.append({"id": str(country.id), "code": clean_code, "kiss24_org_uuid": kiss24_uuid})

        db.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_COUNTRY_SYNC", "KISS24",
                        "N/A", f"Synced {matched_count} Countries.")
        return {"status": "Success",
                "message": f"Successfully updated {matched_count} raw assets with KISS24 Asset IDs.",
                "total_kiss24_mapped": len(orgs_map), "total_raw_assets_updated": matched_count,
                "updated_assets": updated_countries}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def sync_kiss24_asset_ids(db: Session, current_user: dict):
    try:
        onetrust_map = map_asset_onetrust_custom_field()
        if not onetrust_map:
            return {"status": "Success", "message": "No OneTrust asset mappings found in KISS24.",
                    "total_kiss24_mapped": 0, "total_raw_assets_updated": 0}

        assets_metadata = (db.query(RawAssets.id,
                                   RawAssetsSnowMetadata.snow_data['u_onetrust_number'].astext.label('onetrust_id'))
                           .join(RawAssetsSnowMetadata, RawAssets.id == RawAssetsSnowMetadata.correlation_id)
                           .filter(RawAssetsSnowMetadata.snow_data['u_onetrust_number'].astext.isnot(None),
                                   RawAssetsSnowMetadata.snow_data['u_onetrust_number'].astext != '')
                           .all())

        matched_count, updated_assets = 0, []

        for raw_asset_id, onetrust_id in assets_metadata:
            clean_onetrust_id = str(onetrust_id).strip()
            if clean_onetrust_id in onetrust_map:
                kiss24_uuid = onetrust_map[clean_onetrust_id]

                # Fetch and update the actual object
                raw_asset = db.query(RawAssets).filter(RawAssets.id == raw_asset_id).first()
                if raw_asset:
                    raw_asset.kiss24_asset_id = kiss24_uuid
                    raw_asset.update_date = aware_utcnow()
                    matched_count += 1
                    updated_assets.append({"raw_asset_id": str(raw_asset_id), "onetrust_id": clean_onetrust_id,
                                           "kiss24_asset_id": kiss24_uuid})

        db.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_ASSET_SYNC", "KISS24",
                        "N/A", f"Synced {matched_count} Raw Assets.")
        return {"status": "Success", "message": f"Successfully updated {matched_count} raw assets.",
                "total_kiss24_mapped": len(onetrust_map), "total_raw_assets_updated": matched_count,
                "updated_assets": updated_assets}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def sync_update_kiss24_snowid(db: Session, current_user: dict):
    assets = db.query(RawAssets).filter(
        RawAssets.kiss24_asset_id.isnot(None), RawAssets.kiss24_asset_id != '',
        RawAssets.snow_number.isnot(None), RawAssets.snow_number != ''
    ).all()

    if not assets: return {"message": "No eligible assets found to sync.", "results": None}

    asset_dict_payload = {a.kiss24_asset_id: a.snow_number for a in assets}
    try:
        sync_results = add_snowid_to_kiss24asset(asset_dict_payload)
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_SNOW_ID_SYNC", "KISS24",
                        "N/A",
                        f"Pushed ServiceNow IDs to KISS24. Success: {sync_results['success_count']}, Failed: {sync_results['failed_count']}.")
        return {"message": f"Sync complete. Successfully updated {sync_results['success_count']} assets.",
                "results": sync_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def sync_kiss24_vulnerability_types(db: Session, current_user: dict):
    try:
        map_type, map_context = sync_vuln_type_kiss24()

        # Update Contexts
        existing_contexts = {str(c.id): c for c in db.query(Kiss24ContextType).all()}
        for ctx_id, ctx_name in map_context.items():
            if ctx_id in existing_contexts:
                existing_contexts[ctx_id].name = ctx_name
            else:
                db.add(Kiss24ContextType(id=ctx_id, name=ctx_name))

        # Delete missing Contexts
        for c_id in list(existing_contexts.keys()):
            if c_id not in map_context:
                db.delete(existing_contexts[c_id])

        db.flush()  # Ensure contexts exist for relationships

        # Update Vuln Types
        existing_vulns = {str(v.id): v for v in db.query(Kiss24VulnTypes).all()}
        for v_id, v_data in map_type.items():
            if v_id in existing_vulns:
                existing_vulns[v_id].name = v_data["name"]
            else:
                db.add(Kiss24VulnTypes(id=v_id, name=v_data["name"]))

        # Delete missing Vuln Types
        for v_id in list(existing_vulns.keys()):
            if v_id not in map_type:
                db.delete(existing_vulns[v_id])

        db.flush()

        # Update Associations (Many-to-Many)
        db.execute(kiss24_vuln_context_association.delete())

        association_values = [{"vuln_id": v_id, "context_id": ctx["uuid"]} for v_id, v_data in map_type.items() for ctx
                              in v_data.get("contexts", [])]

        if association_values:
            db.execute(kiss24_vuln_context_association.insert().values(association_values))

        db.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_VULN_TYPE_SYNC", "KISS24",
                        "N/A",
                        f"Synced {len(map_context)} Contexts, {len(map_type)} Vuln Types, and {len(association_values)} Connections.")
        return {"status": "Success", "message": "Many-to-Many Synchronization complete.",
                "contexts_synced": len(map_context), "vuln_types_synced": len(map_type),
                "associations_created": len(association_values)}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def sync_user_kiss24_uuid(db: Session, current_user: dict):
    try:
        users = db.query(Users).filter(Users.end_week.is_(None), Users.end_year.is_(None)).all()
        email_list = [u.email for u in users]
        if not email_list: return {"message": "No active users found to sync.", "updated_count": 0}

        sync_dat = map_mario_user_kiss24_uuid(email_list)
        if not sync_dat: return {"message": "No matching users found in Keep Secure 24.", "updated_count": 0}

        updated_count = 0
        for u in users:
            if u.email in sync_dat:
                u.kiss24_uuid = sync_dat[u.email]
                updated_count += 1

        db.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_USER_UUID_SYNC", "USERS",
                        "N/A", f"Synced {updated_count} users.")
        return {"status": "Success", "message": f"Successfully updated {updated_count} users.",
                "updated_count": updated_count, "mapped_emails": list(sync_dat.keys())}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- TEST OPERATIONS ---
def create_kiss24_test(db: Session, test_id: str, current_user: dict):
    try:
        test = db.query(Tests).filter(Tests.id == test_id).first()
        if not test: raise HTTPException(status_code=404, detail="Test not found.")

        check_maintainer_lane_access(current_user, str(test.service_lane_id))

        if test.kiss24: raise HTTPException(status_code=400, detail="Test is already registered in Keep Secure 24.")
        if not test.start_year or not test.start_week: raise HTTPException(status_code=400,
                                                                           detail="Test must be scheduled before creation.")

        # Traverse relationships safely
        country_uuid = None
        asset_uuid = None

        first_asset = (db.query(RawAssets, Country)
                       .join(Assets, RawAssets.id == Assets.raw_asset_id)
                       .join(TestAssets, Assets.id == TestAssets.asset_id)
                       .join(Country, RawAssets.country_id == Country.id)
                       .filter(TestAssets.test_id == test_id).first())

        if first_asset:
            country_uuid = first_asset.Country.kiss24_uuid
            asset_uuid = first_asset.RawAssets.kiss24_asset_id

        if not country_uuid or not asset_uuid:
            raise HTTPException(status_code=400, detail="Missing Country UUID or Asset ID.")

        user_api_key = get_user_kiss24_key(db, str(current_user["id"]))
        start_date_str = datetime.fromisocalendar(test.start_year, test.start_week, 1).strftime("%Y-%m-%d")

        service_name = test.services_lanes.name if test.services_lanes else 'Unknown Service'
        full_test_name = f"{test.name} - {service_name} {test.start_year}"

        payload = {"details": "to do", "scheduled_start": start_date_str, "auto_start": True, "private": False,
                   "light": False, "assets": [str(asset_uuid)], "name": full_test_name}
        new_test_uuid = create_test(str(country_uuid), payload, user_api_key)

        if not new_test_uuid: raise HTTPException(status_code=500,
                                                  detail="KISS24 API did not return a valid Test UUID.")

        test.kiss24 = new_test_uuid
        db.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_TEST_CREATED", "KISS24",
                        str(test_id), f"Created Keep Secure 24 Test: {new_test_uuid}")
        return {"status": "Success", "kiss24_uuid": new_test_uuid, "message": "Test successfully created in KISS24!"}
    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def get_kiss24_live_status(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found.")
    if not test.kiss24: raise HTTPException(status_code=404, detail="Not linked to Keep Secure 24.")

    check_maintainer_lane_access(current_user, str(test.service_lane_id))
    raw_data = get_test_info(str(test.kiss24))
    if not raw_data or not raw_data.get("items"): raise HTTPException(status_code=404,
                                                                      detail="Test missing from KISS24 API.")

    item = raw_data["items"][0]
    return {
        "id": item.get("id"), "name": item.get("name"), "state": item.get("state"), "light": item.get("light"),
        "scheduled_date": item.get("scheduled_date"), "organisation_name": (item.get("organisation") or {}).get("name"),
        "requested_at": item.get("requested_at"), "requested_by_email": (item.get("requested_by") or {}).get("email"),
        "started_at": item.get("started_at"), "started_by_email": (item.get("started_by") or {}).get("email"),
        "ended_at": item.get("ended_at"), "ended_by_email": (item.get("ended_by") or {}).get("email")
    }


def get_kiss24_vulnerabilities(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test or not test.kiss24: raise HTTPException(status_code=404, detail="Not linked to Keep Secure 24.")

    check_maintainer_lane_access(current_user, str(test.service_lane_id))
    raw_data = get_test_vulns_info(str(test.kiss24))
    if not raw_data or not raw_data.get("items"): return []

    return [{
        "uuid": item.get("uuid"), "id": item.get("id"), "description": item.get("description"),
        "state": item.get("state"), "severity": item.get("severity"), "created_at": item.get("created_at"),
        "created_by_name": (item.get("created_by") or {}).get("name"), "published_at": item.get("published_at"),
        "published_by_name": (item.get("published_by") or {}).get("name")
    } for item in raw_data["items"]]


def get_kiss24_vuln_types_for_dropdown(db: Session):
    vuln_types = db.query(Kiss24VulnTypes).all()

    vuln_dict = {}
    for vt in vuln_types:
        vt_id_str = str(vt.id)
        if vt_id_str not in vuln_dict:
            vuln_dict[vt_id_str] = {"id": vt_id_str, "name": vt.name, "contexts": []}

        for ctx in vt.contexts:
            vuln_dict[vt_id_str]["contexts"].append({"id": str(ctx.id), "name": ctx.name})

    return list(vuln_dict.values())


def publish_vulnerability(db: Session, test_id: str, payload: dict, current_user: dict):
    try:
        test = db.query(Tests).filter(Tests.id == test_id).first()
        if not test or not test.kiss24:
            raise HTTPException(status_code=400, detail="Test is missing required Keep Secure 24 UUIDs.")

        country_uuid = None
        asset_uuid = None

        first_asset = (db.query(RawAssets, Country)
                       .join(Assets, RawAssets.id == Assets.raw_asset_id)
                       .join(TestAssets, Assets.id == TestAssets.asset_id)
                       .join(Country, RawAssets.country_id == Country.id)
                       .filter(TestAssets.test_id == test_id).first())

        if first_asset:
            country_uuid = first_asset.Country.kiss24_uuid
            asset_uuid = first_asset.RawAssets.kiss24_asset_id

        if not country_uuid or not asset_uuid:
            raise HTTPException(status_code=400, detail="Missing Country UUID or Asset ID.")

        check_maintainer_lane_access(current_user, str(test.service_lane_id))
        user_api_key = get_user_kiss24_key(db, str(current_user["id"]))

        cvss_map = {
            "info": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:N/VI:N/VA:N/SC:N/SI:N/SA:N",
            "low": "CVSS:4.0/AV:N/AC:H/AT:N/PR:L/UI:N/VC:L/VI:L/VA:L/SC:N/SI:N/SA:N",
            "medium": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:L/VI:L/VA:L/SC:N/SI:N/SA:N",
            "high": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:L/VA:L/SC:N/SI:N/SA:N",
            "critical": "CVSS:4.0/AV:N/AC:L/AT:N/PR:N/UI:N/VC:H/VI:H/VA:H/SC:N/SI:N/SA:N"
        }
        severity_key = str(payload.get("severity", "info")).lower()
        cvss_vector = cvss_map.get(severity_key, cvss_map["info"])

        safe_html = re.sub(r'<pre.*?</pre>', lambda m: m.group(0).replace('\n', '<br/>'), str(payload.get("html", "")),
                           flags=re.IGNORECASE | re.DOTALL)
        safe_html = safe_html.replace('\n', '').replace('\r', '')
        safe_html = re.sub(r'<p>\s*(?:&nbsp;|<br\s*/?>)*\s*</p>', '', safe_html, flags=re.IGNORECASE)
        safe_html = re.sub(r'<li>\s*(?:&nbsp;|<br\s*/?>)*\s*</li>', '', safe_html, flags=re.IGNORECASE)

        remediation_uuid = get_custom_fields_choice_uuid(str(country_uuid), "Remediation Effort",
                                                         payload.get("remediation_effort", "Minimal"))
        custom_fields = [{"parent": "MITRE ID", "text": payload.get("mitre_id", "")}]
        if remediation_uuid: custom_fields.append({"parent": "Remediation Effort", "choices": remediation_uuid})

        create_payload = {
            "asset": str(asset_uuid), "vulnerability_type": payload.get("vulnerability_type"),
            "context": payload.get("context"),
            "test": str(test.kiss24), "severity": severity_key, "description": payload.get("title"),
            "details": safe_html,
            "ready_to_publish": True, "cvss_vector": cvss_vector, "authenticated": payload.get("authenticated", False),
            "custom_fields": custom_fields
        }

        new_vuln_uuid = create_vulnerability(str(country_uuid), create_payload, user_api_key)
        if not new_vuln_uuid: raise HTTPException(status_code=500, detail="Failed to create vulnerability.")

        uploaded_count = sum(1 for img in payload.get("images", []) if
                             upload_vulnerability_attachment(new_vuln_uuid, img["base64"], img["name"], user_api_key))
        log_audit_event(str(current_user["id"]), current_user.get("role", "pentester"), "KISS24_VULN_PUBLISHED",
                        "KISS24", new_vuln_uuid, f"Published {severity_key}. Images: {uploaded_count}")
        return {"status": "Success", "message": "Vulnerability Published!", "vuln_uuid": new_vuln_uuid}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- VALIDATING QUEUE ---
def get_validating_vulns(db: Session):
    vulns = db.query(Kiss24ValidatingVulns).order_by(Kiss24ValidatingVulns.updated_at.desc().nullslast()).all()
    return [{
        "uuid": str(v.id), "validating_team": v.validating_team, "need_credentials": v.need_credentials,
        "need_vpn": v.need_vpn, "other_issue": v.other_issue or "", "note": v.note or "",
        "action_taken": v.action_taken or "", "ai_suggestion": v.ai_suggestion or "",
        "updated_at": v.updated_at, "updated_by_name": v.updated_by_name or "N/A"
    } for v in vulns]


def sync_validating_vulns(db: Session, current_user: dict):
    user_api_key = get_user_kiss24_key(db, str(current_user["id"]))
    live_vulns = fetch_validating_vulnerabilities(user_api_key)
    live_uuids = {str(v["uuid"]): v for v in live_vulns}

    existing_vulns = {str(v.id): v for v in db.query(Kiss24ValidatingVulns).all()}

    to_delete = set(existing_vulns.keys()) - set(live_uuids.keys())
    to_insert = set(live_uuids.keys()) - set(existing_vulns.keys())

    # Delete
    for uid in to_delete:
        db.delete(existing_vulns[uid])

    # Insert
    for uid in to_insert:
        team = "DevoTeam" if (live_uuids[uid].get("created_by") or {}).get("email", "").endswith(
            "@devoteam.com") else "Gost"
        new_vuln = Kiss24ValidatingVulns(id=uid, validating_team=team)
        db.add(new_vuln)
        existing_vulns[uid] = new_vuln

    db.commit()

    return [{
        "uuid": uid, "id": live_data.get("id"), "description": live_data.get("description"),
        "severity": live_data.get("severity"), "sub_state": live_data.get("sub_state", ""),
        "vuln_type": (live_data.get("vulnerability_type") or {}).get("name", "Unknown"),
        "test_id": (live_data.get("test") or {}).get("id", "Unknown"),
        "organization": (live_data.get("organisation") or {}).get("name", "Unknown"),
        "asset": (live_data.get("asset") or {}).get("name", "Unknown"), "validating_team": local_data.validating_team,
        "need_credentials": local_data.need_credentials, "need_vpn": local_data.need_vpn,
        "other_issue": local_data.other_issue or "",
        "note": local_data.note or "", "action_taken": local_data.action_taken or "",
        "ai_suggestion": local_data.ai_suggestion or "", "updated_at": local_data.updated_at,
        "updated_by_name": local_data.updated_by_name or "N/A"
    } for uid, live_data in live_uuids.items() if (local_data := existing_vulns.get(uid))]


def update_validating_vuln(db: Session, uuid: str, payload: dict, current_user: dict):
    vuln = db.query(Kiss24ValidatingVulns).filter(Kiss24ValidatingVulns.id == uuid).first()
    if vuln:
        vuln.need_credentials = payload.get("need_credentials", False)
        vuln.need_vpn = payload.get("need_vpn", False)
        vuln.other_issue = payload.get("other_issue", "")
        vuln.note = payload.get("note", "")
        vuln.action_taken = payload.get("action_taken", "")
        vuln.updated_at = aware_utcnow()
        vuln.updated_by_name = current_user["name"]
        db.commit()
    return {"message": "Updated successfully"}


def upload_attachment_to_gcs(att_uuid: str, file_name: str, vuln_uuid: str, bucket, user_api_key: str) -> str | None:
    try:
        resp = requests.get(f"{KISS_24_ENDPOINT}attachments/{att_uuid}",
                            headers={"x-api-key": user_api_key, "Content-Type": "application/json"})
        if resp.status_code == 200:
            blob_name = f"{vuln_uuid}/{att_uuid}_{file_name}"
            bucket.blob(blob_name).upload_from_string(resp.content)
            return f"gs://{KISS_24_TEMP_BUCKET}/{blob_name}"
        log_audit_event("SYSTEM", "SYSTEM", "KISS24_GCS_UPLOAD", "GCS", "N/A",
                        f"Failed to download attachment {att_uuid}. Status: {resp.status_code}")
    except Exception as e:
        log_audit_event("SYSTEM", "SYSTEM", "KISS24_GCS_UPLOAD_ERROR", "GCS", "N/A",
                        f"Crash during GCS upload for {file_name}: {str(e)}")
    return None


def trigger_luigi_verification_pipeline(vuln_uuid: str, user_api_key: str):
    try:
        vuln_data = fetch_validation_info(vuln_uuid, user_api_key)
        if not vuln_data: return

        bucket = storage.Client().bucket(KISS_24_TEMP_BUCKET)
        gcs_uris_to_cleanup = []

        for att in vuln_data.get("downloaded_attachments", []) + [ca for c in vuln_data.get("fetched_comments", []) for
                                                                  ca in c.get("downloaded_attachments", [])]:
            if uri := upload_attachment_to_gcs(att["uuid"], att["name"], vuln_uuid, bucket, user_api_key):
                att["gcs_uri"], _ = uri, gcs_uris_to_cleanup.append(uri)

        payload = {"task": "VERIFY_VULN", "vuln_uuid": vuln_uuid, "vuln_data": vuln_data,
                   "cleanup_uris": gcs_uris_to_cleanup}
        message_id = pubsub_v1.PublisherClient().publish(PUBSUB_TOPIC_PATH,
                                                         json.dumps(payload).encode("utf-8")).result()
        log_audit_event("SYSTEM", "SYSTEM", "LUIGI_PIPELINE_SUCCESS", "PIPELINE", "N/A",
                        f"Message published! ID: {message_id}")
    except Exception as e:
        log_audit_event("SYSTEM", "SYSTEM", "LUIGI_PIPELINE_CRASH", "PIPELINE", "N/A",
                        f"Pipeline CRASHED for {vuln_uuid}: {str(e)}")


# --- RECONCILIATION ---
def get_reconciliation_candidates(db: Session, limit: int):
    kiss24_unmapped_by_org = get_unmapped_kiss24_assets(get_secret(KISS_24_API_KEY_NAME))

    query = (db.query(RawAssets, Country.kiss24_uuid.label("org_uuid"), Country.name.label("country_name"))
    .join(Country, RawAssets.country_id == Country.id)
    .filter(
        RawAssets.snow_number.isnot(None), RawAssets.snow_number != '',
        or_(RawAssets.kiss24_asset_id.is_(None), RawAssets.kiss24_asset_id == ''),
        Country.kiss24_uuid.isnot(None)
    ))

    results = []
    for asset, org_uuid, country_name in query.all():
        suggestions = sorted(
            [{"kiss24_uuid": cand["uuid"], "kiss24_name": cand["name"],
              "score": calculate_similarity(asset.name, cand["name"])}
             for cand in kiss24_unmapped_by_org.get(org_uuid, [])],
            key=lambda x: x["score"], reverse=True
        )[:5]

        results.append({
            "mario_raw_asset_id": str(asset.id), "mario_name": asset.name, "snow_number": asset.snow_number,
            "country_name": country_name, "org_uuid": org_uuid, "top_suggestions": suggestions
        })
        if limit > 0 and len(results) >= limit: break

    return results


def reconcile_asset(db: Session, payload, current_user: dict):
    if not payload.mario_raw_asset_id or not payload.kiss24_uuid or not payload.snow_number:
        raise HTTPException(status_code=400, detail="Missing required fields.")

    push_results = add_snowid_to_kiss24asset({payload.kiss24_uuid: payload.snow_number})
    if push_results["failed_count"] > 0:
        raise HTTPException(status_code=500, detail=f"Keep Secure 24 rejected the update: {push_results['errors']}")

    asset = db.query(RawAssets).filter(RawAssets.id == payload.mario_raw_asset_id).first()
    if asset:
        asset.kiss24_asset_id = payload.kiss24_uuid
        asset.update_date = aware_utcnow()
        db.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "ASSET_RECONCILED", "KISS24",
                    payload.mario_raw_asset_id,
                    f"Manually linked SNow {payload.snow_number} to KISS24 {payload.kiss24_uuid}")
    return {"status": "Success", "message": "Assets successfully linked!"}


def bulk_reconcile_assets(db: Session, payload, current_user: dict):
    if not payload.assets: raise HTTPException(status_code=400, detail="No assets provided.")

    push_results = add_snowid_to_kiss24asset({item.kiss24_uuid: item.snow_number for item in payload.assets})

    for item in payload.assets:
        asset = db.query(RawAssets).filter(RawAssets.id == item.mario_raw_asset_id).first()
        if asset:
            asset.kiss24_asset_id = item.kiss24_uuid
            asset.update_date = aware_utcnow()

    db.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "ASSET_RECONCILED_BULK", "KISS24", "BULK",
                    f"Manually linked {len(payload.assets)} assets to Keep Secure 24.")

    if push_results["failed_count"] > 0:
        return {"status": "Partial",
                "message": f"Linked {push_results['success_count']} assets. {push_results['failed_count']} failed.",
                "errors": push_results["errors"]}
    return {"status": "Success", "message": f"Successfully linked {push_results['success_count']} assets!"}


def get_kiss24_synced_raw_assets_paginated(db: Session, current_user: dict, page: int, limit: int,
                                       search: str = None, sort_by: str = "name", sort_dir: str = "asc"):
    offset = (page - 1) * limit

    base_query = db.query(RawAssets)
    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        base_query = base_query.filter(RawAssets.service_forecast_id == str(lane_id))

    total_assets = base_query.count()

    synced_query = (db.query(
        RawAssets.id, RawAssets.name, RawAssets.snow_number, RawAssets.kiss24_asset_id, Country.name.label("country_name")
    ).outerjoin(Country, RawAssets.country_id == Country.id)
     .filter(and_(RawAssets.kiss24_asset_id.isnot(None), RawAssets.kiss24_asset_id != "")))

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        synced_query = synced_query.filter(RawAssets.service_forecast_id == str(lane_id))

    # --- Apply Filters ---
    if search:
        synced_query = synced_query.filter(
            or_(
                RawAssets.name.ilike(f"%{search}%"),
                Country.name.ilike(f"%{search}%")
            )
        )

    total_synced = synced_query.count()

    # --- Apply Sorting ---
    order_col = Country.name if sort_by == "country" else RawAssets.name
    order_col = order_col.desc() if sort_dir == "desc" else order_col.asc()

    rows = synced_query.order_by(order_col).offset(offset).limit(limit).all()

    items = [{
        "id": str(r.id), "name": r.name, "snow_number": r.snow_number,
        "country_name": r.country_name, "kiss24_asset_id": r.kiss24_asset_id
    } for r in rows]

    return {
        "total_assets": total_assets,
        "total_synced": total_synced,
        "items": items,
        "page": page,
        "limit": limit,
        "total_pages": (total_synced + limit - 1) // limit
    }


def get_kiss24_synced_tests_paginated(db: Session, current_user: dict, page: int, limit: int,
                                      search: str = None, service_lane: str = None, status: str = None,
                                      sort_by: str = "name", sort_dir: str = "asc"):
    offset = (page - 1) * limit

    base_query = db.query(Tests).join(ServiceLanes, Tests.service_lane_id == ServiceLanes.id).filter(ServiceLanes.auto_provision_workspace == True)
    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        base_query = base_query.filter(Tests.service_lane_id == str(lane_id))

    total_tests = base_query.count()

    synced_query = (db.query(
        Tests.id, Tests.name, Tests.stages, Tests.kiss24, ServiceLanes.name.label("service_lane_name")
    ).join(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
     .filter(ServiceLanes.auto_provision_workspace == True, Tests.kiss24.isnot(None)))

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        synced_query = synced_query.filter(Tests.service_lane_id == str(lane_id))

    # --- Apply Filters ---
    if search:
        synced_query = synced_query.filter(Tests.name.ilike(f"%{search}%"))
    if service_lane:
        synced_query = synced_query.filter(ServiceLanes.name.ilike(f"%{service_lane}%"))
    if status:
        # Match enum by name mapping
        enum_val = getattr(TestStages, status, None)
        if enum_val:
            synced_query = synced_query.filter(Tests.stages == enum_val)

    total_synced = synced_query.count()

    # --- Apply Sorting ---
    if sort_by == "service_lane":
        order_col = ServiceLanes.name
    elif sort_by == "status":
        order_col = Tests.stages
    else:
        order_col = Tests.name

    order_col = order_col.desc() if sort_dir == "desc" else order_col.asc()

    rows = synced_query.order_by(order_col).offset(offset).limit(limit).all()

    items = [{
        "id": str(r.id), "name": r.name, "stages": r.stages.name if r.stages else None,
        "service_lane": r.service_lane_name, "kiss24": str(r.kiss24)
    } for r in rows]

    return {
        "total_tests": total_tests,
        "total_synced": total_synced,
        "items": items,
        "page": page,
        "limit": limit,
        "total_pages": (total_synced + limit - 1) // limit
    }