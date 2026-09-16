import os
import re
import json
import difflib
import requests
from datetime import datetime
from fastapi import HTTPException, status
from google.cloud import pubsub_v1, storage
from audit_logger import log_audit_event
from utils.secret_manager import get_secret
from utils.security_cipher import get_cipher
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


def get_user_kiss24_key(cursor, user_id: str) -> str:
    cursor.execute("SELECT kiss24_api_key FROM users WHERE id = %s", (user_id,))
    key_row = cursor.fetchone()
    if not key_row or not key_row[0]:
        raise HTTPException(status_code=400, detail="Configure your personal Keep Secure 24 API key first.")
    cipher = get_cipher()
    try:
        return cipher.decrypt(key_row[0].encode('utf-8')).decode('utf-8')
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
def sync_kiss24_org_ids(cursor, current_user: dict):
    try:
        orgs_map = map_organizations()
        if not orgs_map:
            return {"status": "Success", "message": "No Organization mappings found in KISS24.",
                    "total_kiss24_mapped": 0, "total_countries_updated": 0}

        cursor.execute("SELECT id, code FROM countries WHERE code IS NOT NULL")
        matched_count, updated_countries = 0, []

        for cid, code in cursor.fetchall():
            clean_code = str(code).strip()
            if clean_code in orgs_map:
                kiss24_uuid = orgs_map[clean_code]
                cursor.execute("UPDATE countries SET kiss24_uuid = %s WHERE id = %s", (kiss24_uuid, str(cid)))
                matched_count += 1
                updated_countries.append({"id": str(cid), "code": clean_code, "kiss24_org_uuid": kiss24_uuid})

        cursor.connection.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_COUNTRY_SYNC", "KISS24",
                        "N/A", f"Synced {matched_count} Countries.")
        return {"status": "Success",
                "message": f"Successfully updated {matched_count} raw assets with KISS24 Asset IDs.",
                "total_kiss24_mapped": len(orgs_map), "total_raw_assets_updated": matched_count,
                "updated_assets": updated_countries}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def sync_kiss24_asset_ids(cursor, current_user: dict):
    try:
        onetrust_map = map_asset_onetrust_custom_field()
        if not onetrust_map:
            return {"status": "Success", "message": "No OneTrust asset mappings found in KISS24.",
                    "total_kiss24_mapped": 0, "total_raw_assets_updated": 0}

        cursor.execute("""
            SELECT r.id, s.snow_data->>'u_onetrust_number' AS onetrust_id
            FROM raw_assets r JOIN raw_assets_snow_metadata s ON r.id = s.correlation_id
            WHERE s.snow_data->>'u_onetrust_number' IS NOT NULL AND s.snow_data->>'u_onetrust_number' != ''
        """)
        matched_count, updated_assets = 0, []

        for raw_asset_id, onetrust_id in cursor.fetchall():
            clean_onetrust_id = str(onetrust_id).strip()
            if clean_onetrust_id in onetrust_map:
                kiss24_uuid = onetrust_map[clean_onetrust_id]
                cursor.execute("UPDATE raw_assets SET kiss24_asset_id = %s, update_date = NOW() WHERE id = %s",
                               (kiss24_uuid, str(raw_asset_id)))
                matched_count += 1
                updated_assets.append({"raw_asset_id": str(raw_asset_id), "onetrust_id": clean_onetrust_id,
                                       "kiss24_asset_id": kiss24_uuid})

        cursor.connection.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_ASSET_SYNC", "KISS24",
                        "N/A", f"Synced {matched_count} Raw Assets.")
        return {"status": "Success", "message": f"Successfully updated {matched_count} raw assets.",
                "total_kiss24_mapped": len(onetrust_map), "total_raw_assets_updated": matched_count,
                "updated_assets": updated_assets}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def sync_update_kiss24_snowid(cursor, current_user: dict):
    cursor.execute("""
        SELECT kiss24_asset_id, snow_number FROM raw_assets
        WHERE kiss24_asset_id IS NOT NULL AND kiss24_asset_id != '' AND snow_number IS NOT NULL AND snow_number != ''
    """)
    rows = cursor.fetchall()
    if not rows: return {"message": "No eligible assets found to sync.", "results": None}

    asset_dict_payload = {row[0]: row[1] for row in rows}
    try:
        sync_results = add_snowid_to_kiss24asset(asset_dict_payload)
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_SNOW_ID_SYNC", "KISS24",
                        "N/A",
                        f"Pushed ServiceNow IDs to KISS24. Success: {sync_results['success_count']}, Failed: {sync_results['failed_count']}.")
        return {"message": f"Sync complete. Successfully updated {sync_results['success_count']} assets.",
                "results": sync_results}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


def sync_kiss24_vulnerability_types(cursor, current_user: dict):
    try:
        map_type, map_context = sync_vuln_type_kiss24()

        for ctx_id, ctx_name in map_context.items():
            cursor.execute(
                "INSERT INTO kiss24_context (id, name) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name",
                (ctx_id, ctx_name))

        if map_context:
            format_strings = ','.join(['%s'] * len(map_context))
            cursor.execute(f"DELETE FROM kiss24_context WHERE id NOT IN ({format_strings})", tuple(map_context.keys()))
        else:
            cursor.execute("DELETE FROM kiss24_context")

        for v_id, v_data in map_type.items():
            cursor.execute(
                "INSERT INTO kiss24_vuln_types (id, name) VALUES (%s, %s) ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name",
                (v_id, v_data["name"]))

        if map_type:
            format_strings = ','.join(['%s'] * len(map_type))
            cursor.execute(f"DELETE FROM kiss24_vuln_types WHERE id NOT IN ({format_strings})", tuple(map_type.keys()))
        else:
            cursor.execute("DELETE FROM kiss24_vuln_types")

        cursor.execute("DELETE FROM kiss24_vuln_context_association")
        association_values = [(v_id, ctx["uuid"]) for v_id, v_data in map_type.items() for ctx in
                              v_data.get("contexts", [])]

        if association_values:
            cursor.executemany(
                "INSERT INTO kiss24_vuln_context_association (vuln_id, context_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                association_values)

        cursor.connection.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_VULN_TYPE_SYNC", "KISS24",
                        "N/A",
                        f"Synced {len(map_context)} Contexts, {len(map_type)} Vuln Types, and {len(association_values)} Connections.")
        return {"status": "Success", "message": "Many-to-Many Synchronization complete.",
                "contexts_synced": len(map_context), "vuln_types_synced": len(map_type),
                "associations_created": len(association_values)}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def sync_user_kiss24_uuid(cursor, current_user: dict):
    try:
        cursor.execute("SELECT email FROM users WHERE end_week IS NULL and end_year IS NULL")
        email_list = [row[0] for row in cursor.fetchall()]
        if not email_list: return {"message": "No active users found to sync.", "updated_count": 0}

        sync_dat = map_mario_user_kiss24_uuid(email_list)
        if not sync_dat: return {"message": "No matching users found in Keep Secure 24.", "updated_count": 0}

        updated_count = 0
        for email, kiss_uuid in sync_dat.items():
            cursor.execute("UPDATE users SET kiss24_uuid = %s WHERE email = %s", (kiss_uuid, email))
            updated_count += cursor.rowcount

        cursor.connection.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_USER_UUID_SYNC", "USERS",
                        "N/A", f"Synced {updated_count} users.")
        return {"status": "Success", "message": f"Successfully updated {updated_count} users.",
                "updated_count": updated_count, "mapped_emails": list(sync_dat.keys())}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- TEST OPERATIONS ---
def create_kiss24_test(cursor, test_id: str, current_user: dict):
    try:
        cursor.execute("""
            SELECT t.name, t.start_year, t.start_week, t.kiss24, t.service_lane_id, sl.name, c.kiss24_uuid, ra.kiss24_asset_id
            FROM tests t LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id LEFT JOIN test_assets ta ON t.id = ta.test_id
            LEFT JOIN assets a ON ta.asset_id = a.id LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id LEFT JOIN countries c ON ra.country_id = c.id
            WHERE t.id = %s LIMIT 1
        """, (test_id,))
        row = cursor.fetchone()

        if not row: raise HTTPException(status_code=404, detail="Test not found.")
        test_name, start_year, start_week, existing_kiss24, t_lane_id, service_lane, country_uuid, asset_uuid = row

        check_maintainer_lane_access(current_user, str(t_lane_id))
        if existing_kiss24: raise HTTPException(status_code=400, detail="Test is already registered in Keep Secure 24.")
        if not country_uuid or not asset_uuid: raise HTTPException(status_code=400,
                                                                   detail="Missing Country UUID or Asset ID.")
        if not start_year or not start_week: raise HTTPException(status_code=400,
                                                                 detail="Test must be scheduled before creation.")

        user_api_key = get_user_kiss24_key(cursor, str(current_user["id"]))
        start_date_str = datetime.fromisocalendar(start_year, start_week, 1).strftime("%Y-%m-%d")
        full_test_name = f"{test_name} - {service_lane or 'Unknown Service'} {start_year}"

        payload = {"details": "to do", "scheduled_start": start_date_str, "auto_start": True, "private": False,
                   "light": False, "assets": [str(asset_uuid)], "name": full_test_name}
        new_test_uuid = create_test(str(country_uuid), payload, user_api_key)

        if not new_test_uuid: raise HTTPException(status_code=500,
                                                  detail="KISS24 API did not return a valid Test UUID.")

        cursor.execute("UPDATE tests SET kiss24 = %s WHERE id = %s", (new_test_uuid, test_id))
        cursor.connection.commit()
        log_audit_event(str(current_user["id"]), current_user.get("role", "admin"), "KISS24_TEST_CREATED", "KISS24",
                        str(test_id), f"Created Keep Secure 24 Test: {new_test_uuid}")
        return {"status": "Success", "kiss24_uuid": new_test_uuid, "message": "Test successfully created in KISS24!"}
    except HTTPException:
        raise
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))


def get_kiss24_live_status(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT kiss24, service_lane_id FROM tests WHERE id = %s", (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    if not row[0]: raise HTTPException(status_code=404, detail="Not linked to Keep Secure 24.")

    check_maintainer_lane_access(current_user, str(row[1]))
    raw_data = get_test_info(str(row[0]))
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


def get_kiss24_vulnerabilities(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT kiss24, service_lane_id FROM tests WHERE id = %s", (test_id,))
    row = cursor.fetchone()
    if not row or not row[0]: raise HTTPException(status_code=404, detail="Not linked to Keep Secure 24.")

    check_maintainer_lane_access(current_user, str(row[1]))
    raw_data = get_test_vulns_info(str(row[0]))
    if not raw_data or not raw_data.get("items"): return []

    return [{
        "uuid": item.get("uuid"), "id": item.get("id"), "description": item.get("description"),
        "state": item.get("state"), "severity": item.get("severity"), "created_at": item.get("created_at"),
        "created_by_name": (item.get("created_by") or {}).get("name"), "published_at": item.get("published_at"),
        "published_by_name": (item.get("published_by") or {}).get("name")
    } for item in raw_data["items"]]


def get_kiss24_vuln_types_for_dropdown(cursor):
    cursor.execute("""
        SELECT vt.id, vt.name, c.id, c.name FROM kiss24_vuln_types vt
        LEFT JOIN kiss24_vuln_context_association vca ON vt.id = vca.vuln_id
        LEFT JOIN kiss24_context c ON vca.context_id = c.id ORDER BY vt.name
    """)
    vuln_dict = {}
    for vt_id, vt_name, c_id, c_name in cursor.fetchall():
        vt_id_str = str(vt_id)
        if vt_id_str not in vuln_dict: vuln_dict[vt_id_str] = {"id": vt_id_str, "name": vt_name, "contexts": []}
        if c_id: vuln_dict[vt_id_str]["contexts"].append({"id": str(c_id), "name": c_name})
    return list(vuln_dict.values())


def publish_vulnerability(cursor, test_id: str, payload: dict, current_user: dict):
    try:
        cursor.execute("""
            SELECT t.kiss24, c.kiss24_uuid, ra.kiss24_asset_id, t.service_lane_id
            FROM tests t LEFT JOIN test_assets ta ON t.id = ta.test_id LEFT JOIN assets a ON ta.asset_id = a.id
            LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id LEFT JOIN countries c ON ra.country_id = c.id
            WHERE t.id = %s LIMIT 1
        """, (test_id,))
        row = cursor.fetchone()
        if not row or not row[0] or not row[1] or not row[2]: raise HTTPException(status_code=400,
                                                                                  detail="Test is missing required Keep Secure 24 UUIDs.")
        test_uuid, country_uuid, asset_uuid, t_lane_id = row

        check_maintainer_lane_access(current_user, str(t_lane_id))
        user_api_key = get_user_kiss24_key(cursor, str(current_user["id"]))

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
            "test": str(test_uuid), "severity": severity_key, "description": payload.get("title"), "details": safe_html,
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
        cursor.connection.rollback()
        raise HTTPException(status_code=500, detail=str(e))


# --- VALIDATING QUEUE ---
def get_validating_vulns(cursor):
    cursor.execute(
        "SELECT uuid, validating_team, need_credentials, need_vpn, other_issue, note, action_taken, ai_suggestion, updated_at, updated_by_name FROM kiss24_validating_vulns ORDER BY updated_at DESC NULLS LAST")
    return [{"uuid": str(r[0]), "validating_team": r[1], "need_credentials": r[2], "need_vpn": r[3],
             "other_issue": r[4] or "", "note": r[5] or "", "action_taken": r[6] or "", "ai_suggestion": r[7] or "",
             "updated_at": r[8], "updated_by_name": r[9] or "N/A"} for r in cursor.fetchall()]


def sync_validating_vulns(cursor, current_user: dict):
    user_api_key = get_user_kiss24_key(cursor, str(current_user["id"]))
    live_vulns = fetch_validating_vulnerabilities(user_api_key)
    live_uuids = {str(v["uuid"]): v for v in live_vulns}

    cursor.execute(
        "SELECT uuid, validating_team, need_credentials, need_vpn, other_issue, note, action_taken, ai_suggestion, updated_at, updated_by_name FROM kiss24_validating_vulns")
    db_map = {str(r[0]): r for r in cursor.fetchall()}

    to_delete = set(db_map.keys()) - set(live_uuids.keys())
    to_insert = set(live_uuids.keys()) - set(db_map.keys())

    if to_delete:
        cursor.execute(f"DELETE FROM kiss24_validating_vulns WHERE uuid IN ({','.join(['%s'] * len(to_delete))})",
                       tuple(to_delete))

    for uid in to_insert:
        team = "DevoTeam" if (live_uuids[uid].get("created_by") or {}).get("email", "").endswith(
            "@devoteam.com") else "Gost"
        cursor.execute("INSERT INTO kiss24_validating_vulns (uuid, validating_team) VALUES (%s, %s)", (uid, team))
        db_map[uid] = (uid, team, False, False, "", "", "", "", None, "System")

    cursor.connection.commit()

    return [{
        "uuid": uid, "id": live_data.get("id"), "description": live_data.get("description"),
        "severity": live_data.get("severity"),
        "sub_state": live_data.get("sub_state", ""),
        "vuln_type": (live_data.get("vulnerability_type") or {}).get("name", "Unknown"),
        "test_id": (live_data.get("test") or {}).get("id", "Unknown"),
        "organization": (live_data.get("organisation") or {}).get("name", "Unknown"),
        "asset": (live_data.get("asset") or {}).get("name", "Unknown"), "validating_team": local_data[1],
        "need_credentials": local_data[2],
        "need_vpn": local_data[3], "other_issue": local_data[4] or "", "note": local_data[5] or "",
        "action_taken": local_data[6] or "",
        "ai_suggestion": local_data[7] or "", "updated_at": local_data[8], "updated_by_name": local_data[9] or "N/A"
    } for uid, live_data in live_uuids.items() if (local_data := db_map.get(uid))]


def update_validating_vuln(cursor, uuid: str, payload: dict, current_user: dict):
    cursor.execute("""
        UPDATE kiss24_validating_vulns
        SET need_credentials = %s, need_vpn = %s, other_issue = %s, note = %s, action_taken = %s, updated_at = NOW(), updated_by_name = %s
        WHERE uuid = %s
    """, (payload.get("need_credentials", False), payload.get("need_vpn", False), payload.get("other_issue", ""),
          payload.get("note", ""), payload.get("action_taken", ""), current_user["name"], uuid))
    cursor.connection.commit()
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
def get_reconciliation_candidates(cursor, limit: int):
    kiss24_unmapped_by_org = get_unmapped_kiss24_assets(get_secret(KISS_24_API_KEY_NAME))
    cursor.execute("""
        SELECT r.id, r.name, r.snow_number, c.kiss24_uuid, c.name as country_name
        FROM raw_assets r JOIN countries c ON r.country_id = c.id
        WHERE r.snow_number IS NOT NULL AND r.snow_number != '' AND (r.kiss24_asset_id IS NULL OR r.kiss24_asset_id = '') AND c.kiss24_uuid IS NOT NULL
    """)
    results = []
    for r_id, r_name, snow_number, org_uuid, country_name in cursor.fetchall():
        suggestions = sorted([{"kiss24_uuid": cand["uuid"], "kiss24_name": cand["name"],
                               "score": calculate_similarity(r_name, cand["name"])} for cand in
                              kiss24_unmapped_by_org.get(org_uuid, [])], key=lambda x: x["score"], reverse=True)[:5]
        results.append({"mario_raw_asset_id": str(r_id), "mario_name": r_name, "snow_number": snow_number,
                        "country_name": country_name, "org_uuid": org_uuid, "top_suggestions": suggestions})
        if limit > 0 and len(results) >= limit: break
    return results


def reconcile_asset(cursor, payload, current_user: dict):
    if not payload.mario_raw_asset_id or not payload.kiss24_uuid or not payload.snow_number:
        raise HTTPException(status_code=400, detail="Missing required fields.")

    push_results = add_snowid_to_kiss24asset({payload.kiss24_uuid: payload.snow_number})
    if push_results["failed_count"] > 0:
        raise HTTPException(status_code=500, detail=f"Keep Secure 24 rejected the update: {push_results['errors']}")

    cursor.execute("UPDATE raw_assets SET kiss24_asset_id = %s, update_date = NOW() WHERE id = %s",
                   (payload.kiss24_uuid, payload.mario_raw_asset_id))
    cursor.connection.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "ASSET_RECONCILED", "KISS24",
                    payload.mario_raw_asset_id,
                    f"Manually linked SNow {payload.snow_number} to KISS24 {payload.kiss24_uuid}")
    return {"status": "Success", "message": "Assets successfully linked!"}


def bulk_reconcile_assets(cursor, payload, current_user: dict):
    if not payload.assets: raise HTTPException(status_code=400, detail="No assets provided.")

    push_results = add_snowid_to_kiss24asset({item.kiss24_uuid: item.snow_number for item in payload.assets})
    cursor.executemany("UPDATE raw_assets SET kiss24_asset_id = %s, update_date = NOW() WHERE id = %s",
                       [(item.kiss24_uuid, item.mario_raw_asset_id) for item in payload.assets])
    cursor.connection.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "ASSET_RECONCILED_BULK", "KISS24", "BULK",
                    f"Manually linked {len(payload.assets)} assets to Keep Secure 24.")
    if push_results["failed_count"] > 0:
        return {"status": "Partial",
                "message": f"Linked {push_results['success_count']} assets. {push_results['failed_count']} failed.",
                "errors": push_results["errors"]}
    return {"status": "Success", "message": f"Successfully linked {push_results['success_count']} assets!"}