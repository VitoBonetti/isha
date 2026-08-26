import json
import os
import urllib.request
import urllib.error
import requests
import re
from datetime import datetime, timedelta, timezone
from utils.secret_manager import get_secret
from audit_logger import log_audit_event


KISS_24_ENDPOINT = os.environ.get("KISS_24_ENDPOINT")
KISS_24_API_KEY_NAME = os.environ.get("KISS_24_API_KEY_NAME")
CUTOFF_DATE = datetime(2026, 5, 1, tzinfo=timezone.utc)


# --- Keep Secure 24 helper ---
def api_key():
    return str(get_secret(KISS_24_API_KEY_NAME))


def post(endpoint, body=None, page=None):
    url = f"{KISS_24_ENDPOINT}{endpoint}"
    if page:
        url += f"?page={page}"
    data = json.dumps(body or {}).encode("utf-8")
    if page is None and body is None:
        data = b""
    req = urllib.request.Request(url, data=data, headers={"x-api-key": api_key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as res:
        return json.loads(res.read())


# ==========================================
# ---  1. SYSTEM/KISS24 MAPPING SYSTEMS  ---
# ==========================================
# Onetrust/UUID asset Map
def map_asset_onetrust_custom_field():
    map = {}
    page = 1
    total = None
    while True:
        resp = post("fields", {}, page=page)
        if total is None:
            total = resp.get("total", 0)
        for item in resp.get("items", []):
            custom_field = item.get("custom_field", {})
            if custom_field.get("name", "").lower() == "onetrust id" and item.get("value"):
                entity = item.get("entity", {})
                if entity.get("type").lower() == "asset":
                    map[str(item.get("value"))] = entity["uuid"]
        if not resp.get("_links", {}).get("next"):
            break
        page += 1
    return map


# Country Code/UUID Map
def map_organizations():
    map = {}
    page = 1
    total = None
    while True:
        resp = post("provider/organisations", {}, page=page)
        if total is None:
            total = resp.get("total", 0)
        for item in resp.get("items", []):
            prefix = item.get("prefix", "")
            ouuid = item.get("uuid", "")
            map[str(prefix)] = str(ouuid)
        if not resp.get("_links", {}).get("next"):
            break
        page += 1
    return map


# map user and uuid
def map_mario_user_kiss24_uuid(user_emails: list):
    map = {}
    payload = {"emails": user_emails}
    page = 1
    while True:
        resp = post("users", payload, page=page)
        for item in resp.get("items", []):
            is_enabled = item.get("enabled")
            if is_enabled:
                str_email = str(item.get("email", ""))
                str_uuid = str(item.get("uuid", ""))
                map[str(str_email)] = str_uuid
        if not resp.get("_links", {}).get("next"):
            break
        page += 1
    return map


# Add Service Now ID to Assets
def add_snowid_to_kiss24asset(asset_map: dict):
    results = {
        "total_attempted": len(asset_map),
        "success_count": 0,
        "failed_count": 0,
        "errors": []
    }

    for kiss24_id, snow_number in asset_map.items():
        url = f"{KISS_24_ENDPOINT}assets/{kiss24_id}/edit"
        body = {
            "custom_fields": [
                {
                    "parent": "Service Now ID",
                    "text": str(snow_number),
                }
            ]
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(body).encode("utf-8"),
            headers={"x-api-key": api_key(), "Content-Type": "application/json"},
            method="PATCH"
        )

        try:
            with urllib.request.urlopen(req) as res:
                if res.status == 200:
                    results["success_count"] += 1
                else:
                    results["failed_count"] += 1
                    results["errors"].append(f"[{kiss24_id}] Unexpected status: {res.status}")

        except urllib.error.HTTPError as e:
            # Capture the actual API error message from KISS24
            err_body = e.read().decode('utf-8')
            results["failed_count"] += 1
            results["errors"].append(f"[{kiss24_id}] HTTP {e.code}: {err_body}")

        except Exception as e:
            # Catch network timeouts or other generic exceptions
            results["failed_count"] += 1
            results["errors"].append(f"[{kiss24_id}] Error: {str(e)}")

    return results


# Return Context and vulntype maps
def sync_vuln_type_kiss24():
    map_type = {}
    map_context = {}

    # --- Fetch  Vulnerability Types ---
    page = 1
    while True:
        print(f"Fetching Vuln Types: page {page}")
        resp = post("vulnerability-types", {}, page=page)

        for item in resp.get("items", []):
            is_enabled = item.get("enabled")
            if is_enabled:
                type_uuid = item.get("uuid", "")
                map_type[type_uuid] = {
                    "name": item.get("name", ""),
                    "contexts": []  # initialize empty list
                }

        if not resp.get("_links", {}).get("next"):
            break
        page += 1

    # --- Fetch Contexts ---
    page_ctx = 1
    while True:
        resp_ctx = post('provider/contexts', {}, page=page_ctx)

        for item in resp_ctx.get("items", []):
            map_context[item.get("uuid", "")] = item.get("name", "")

        if not resp_ctx.get("_links", {}).get("next"):
            break
        page_ctx += 1

    # ---  Map Relationships Optimized ---
    for context_uuid, context_name in map_context.items():
        page_rel = 1
        while True:
            resp_rel = post("vulnerability-types", {"contexts": [context_uuid]}, page=page_rel)

            for item in resp_rel.get("items", []):
                t_uuid = item.get("uuid")
                if t_uuid in map_type:
                    map_type[t_uuid]["contexts"].append({
                        "uuid": context_uuid,
                        "name": context_name
                    })

            if not resp_rel.get("_links", {}).get("next"):
                break
            page_rel += 1

    return map_type, map_context


# ==========================================
# ---  2. TEST/KISS24 SYNC DATA          ---
# ==========================================
# get test info
def get_test_info(uuid: str):
    endpoint = "tests"
    url = f"{KISS_24_ENDPOINT}{endpoint}"
    payload = {"uuid": [uuid]}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-api-key": api_key(), "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                response_data = json.loads(res.read())
                return response_data
            else:
                return None
    except Exception as e:
        print(f"Failed to fetch test info from KISS24: {e}")
        return None


# Get test vulnerabilities
def get_test_vulns_info(test_uuid: str):
    endpoint = "vulnerabilities"
    url = f"{KISS_24_ENDPOINT}{endpoint}"
    payload = {"tests": [test_uuid]}
    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"x-api-key": api_key(), "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                response_data = json.loads(res.read())
                return response_data
            else:
                return None
    except Exception as e:
        print(f"Failed to fetch vuln information from KISS24 for test {test_uuid}: {e}")
        return None


# Custom field Dynamic Fetcher
def get_custom_fields_choice_uuid(ouuid: str, field_name: str, choice_text: str):
    """Dynamically fetches the specific choice UUID for a given organisation."""
    page = 1
    while True:
        # We use your existing post() helper, filtering by the specific organisation
        resp = post("custom-fields", {"organisations": [ouuid]}, page=page)

        for item in resp.get("items", []):
            if item.get("name", "").lower() == field_name.lower():
                choices = item.get("choices", {}).get("enabled", {})
                for c_uuid, c_text in choices.items():
                    if str(c_text).lower() == str(choice_text).lower():
                        return c_uuid  # Found the exact UUID for this tenant!

        if not resp.get("_links", {}).get("next"):
            break
        page += 1

    return None


# ==========================================
# ---  3. TEST-VULN CREATION ON KISS24   ---
# ==========================================
# Create test
def create_test(ouuid: str, body: dict, user_api_key: str = None):
    endpoint = f"provider/tests/{ouuid}/create"
    url = f"{KISS_24_ENDPOINT}{endpoint}"

    # Use the user's personal key if provided, otherwise fallback to the system key
    # key_to_use = user_api_key if user_api_key else api_key()

    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"x-api-key": user_api_key, "Content-Type": "application/json"}
    )

    with urllib.request.urlopen(req) as res:
        if res.status == 200:
            response_data = json.loads(res.read())
            response_str = str(response_data)
            uuid_pattern = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
            match = re.search(uuid_pattern, response_str)
            if match:
                return match.group(0)
            else:
                return None
        return None


# Create Vuln
def create_vulnerability(ouuid: str, body: dict, user_api_key: str = None):
    endpoint = f"provider/vulnerabilities/{ouuid}/create"
    url = f"{KISS_24_ENDPOINT}{endpoint}"

    # key_to_use = user_api_key if user_api_key else api_key()

    # json.dumps automatically escapes any inner quotes in string variables into \"
    json_data = json.dumps(body).encode("utf-8")

    log_audit_event(
        user_id="SYSTEM",
        role="SYSTEM",
        action="KISS24_VULN_PAYLOAD",
        resource_type="KISS24",
        resource_id="CHECKING_PAYLOAD",
        details=f"Vuln payload: {json_data}"
    )

    req = urllib.request.Request(
        url,
        data=json_data,
        headers={"x-api-key": user_api_key, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                response_data = json.loads(res.read())
                response_str = str(response_data)
                uuid_pattern = r'[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}'
                match = re.search(uuid_pattern, response_str)
                if match:
                    return match.group(0)
        return None
    except urllib.error.HTTPError as e:
        # This explicitly reads the 400 error message from Keep Secure 24 and throws it!
        err_body = e.read().decode('utf-8')
        raise Exception(f"KISS24 Rejected Payload (HTTP {e.code}): {err_body}")
    except Exception as e:
        raise Exception(f"Connection Error: {str(e)}")


def upload_vulnerability_attachment(vuln_uuid: str, base64_data: str, filename: str, user_api_key: str = None):
    endpoint = f"provider/vulnerabilities/{vuln_uuid}/attachment-base64"
    url = f"{KISS_24_ENDPOINT}{endpoint}"

    # key_to_use = user_api_key if user_api_key else api_key()
    payload = {
        "base64": base64_data,
        "name": filename
    }

    req = urllib.request.Request(
        url, data=json.dumps(payload).encode("utf-8"),
        headers={"x-api-key": user_api_key, "Content-Type": "application/json"}
    )
    try:
        with urllib.request.urlopen(req) as res:
            return res.status == 200
    except Exception as e:
        print(f"Failed to upload attachment: {e}")
        return False


# ==========================================
# ---  4. VALIDATIONS                    ---
# ==========================================
# fetchs validating vulns
def fetch_validating_vulnerabilities():
    """Fetches all vulns in 'Validating' state using the system API key with explicit timeouts."""
    all_items = []
    page = 1
    while True:
        payload = {"states": ["Validating"]}
        url = f"{KISS_24_ENDPOINT}vulnerabilities?page={page}"
        data = json.dumps(payload).encode("utf-8")

        req = urllib.request.Request(
            url,
            data=data,
            headers={"x-api-key": api_key(), "Content-Type": "application/json"}
        )

        try:
            # Set a strict 15-second timeout to prevent hanging threads
            with urllib.request.urlopen(req, timeout=15) as res:
                resp = json.loads(res.read())
                items = resp.get("items", [])

                for item in items:
                    if item.get("sub_state") != "Unable to Retest":
                        all_items.append(item)

                # Check pagination bounds
                total_pages = resp.get("page_count", 1)
                if page >= total_pages or not items or not resp.get("_links", {}).get("next"):
                    break
                page += 1

        except urllib.error.HTTPError as e:
            err_body = e.read().decode('utf-8')
            raise Exception(f"KISS24 Error (HTTP {e.code}): {err_body}")
        except Exception as e:
            raise Exception(f"Failed to connect to Keep Secure 24: {str(e)}")

    return all_items


# Complete info and low vulnerabilities workflow
def fetch_validation_info(uuid: str):
    """
    Fetches a single vulnerability, strips out useless metadata to save AI tokens,
    filters for actual developer comments, and structures all attachments perfectly.
    """
    pop_out_list = [
        "original_severity", "overdue", "base_score", "temporal_score", "environmental_score",
        "reopened_count", "due_date", "auto_unpark_at", "review_date_park", "sub_state", "ready_to_publish",
        "jira_issue", "due_date_by", "assignee", "test", "organisation", "asset_groups", "tags",
        "fields", "attachments", "comments", "created_at", "created_by", "last_modified_at", "last_modified_by",
        "published_at", "published_by", "opened_at", "opened_by", "closed_at", "closed_by", "validating_at",
        "validating_by", "last_reopened", "parked_at", "parked_by", "assigned_at", "assigned_by"
    ]
    log_audit_event(
        user_id="SYSTEM",
        role="SYSTEM",
        action="KISS24_GET_ISSUE_TO_VALIDATE",
        resource_type="VALIDATE",
        resource_id="N/A",
        details=f"[AI-VERIFY] Step 1: Fetching KISS24 details for vuln {uuid}.",
    )

    try:
        # 1. Fetch Vulnerability (API expects a list of UUIDs)
        resp = post("vulnerabilities", {"uuid": [uuid]})
        items = resp.get("items", [])
        if not items:
            log_audit_event(
                user_id="SYSTEM",
                role="SYSTEM",
                action="ERROR_KISS24_GET_ISSUE_TO_VALIDATE",
                resource_type="VALIDATE",
                resource_id="N/A",
                details=f"[AI-VERIFY] ERROR: KISS24 returned 0 items for UUID: {uuid}. Raw response: {resp}.",
            )
            return None

        item = items[0]

        # 2. Clean out useless fields for the AI
        for field in pop_out_list:
            item.pop(field, None)

        vuln_uuid = item.get("uuid")
        item["downloaded_attachments"] = []
        item["fetched_comments"] = []
        log_audit_event(
            user_id="SYSTEM",
            role="SYSTEM",
            action="KISS24_GET_ISSUE_TO_VALIDATE_FETCHING_ATTACHMENTS",
            resource_type="VALIDATE",
            resource_id="N/A",
            details=f"[AI-VERIFY] Step 2: Fetching direct attachments for {vuln_uuid}.",
        )

        # 3. Fetch Direct Vulnerability Attachments
        att_resp = post("attachments", {"vulnerabilities": [vuln_uuid]})
        for att in att_resp.get("items", []):
            item["downloaded_attachments"].append({
                "uuid": att.get("uuid"),
                "name": att.get("name"),
                "type": "Vulnerability"
            })
        log_audit_event(
            user_id="SYSTEM",
            role="SYSTEM",
            action="KISS24_GET_ISSUE_TO_VALIDATE_FETCH_COMMENTS",
            resource_type="VALIDATE",
            resource_id="N/A",
            details=f"[AI-VERIFY] Step 3: Fetching comments for {vuln_uuid}.",
        )

        # 4. Fetch Comments
        comm_resp = post("comments", {"vulnerabilities": [vuln_uuid]})
        for comm in comm_resp.get("items", []):

            # FILTER: We only care about human comments, not system state changes!
            if comm.get("comment_type") == "Comment":

                # Keep only what Luigi needs to read
                clean_comm = {
                    "uuid": comm.get("uuid"),
                    "comment": comm.get("comment"),
                    "created_at": comm.get("created_at"),
                    "created_by": comm.get("created_by"),
                    "downloaded_attachments": []
                }

                # 5. Fetch Comment Attachments (Only if total > 0)
                if int(comm.get("attachments", {}).get("total", 0)) > 0:
                    c_att_resp = post("attachments", {"comments": [comm.get("uuid")]})
                    for c_att in c_att_resp.get("items", []):
                        clean_comm["downloaded_attachments"].append({
                            "uuid": c_att.get("uuid"),
                            "name": c_att.get("name"),
                            "type": "Comment"
                        })

                item["fetched_comments"].append(clean_comm)
        log_audit_event(
            user_id="SYSTEM",
            role="SYSTEM",
            action="KISS24_GET_ISSUE_TO_VALIDATE_COMMENTS",
            resource_type="VALIDATE",
            resource_id="N/A",
            details=f"[AI-VERIFY] Success: Extracted {len(item['fetched_comments'])} comments..",
        )
        return item

    except Exception as e:
        log_audit_event(
            user_id="SYSTEM",
            role="SYSTEM",
            action="ERROR_KISS24_GET_ISSUE_TO_VALIDATE",
            resource_type="VALIDATE",
            resource_id="N/A",
            details=f"[AI-VERIFY] CRITICAL CRASH while fetching info for {uuid}: {e}.",
        )
        return None


# ==========================================
# ---  5. REPORTING                      ---
# ==========================================
def fetch_all_kiss24(endpoint: str, api_key: str, payload: dict = None):
    """Helper to fetch all paginated results from KISS24 with safe JSON parsing."""
    if payload is None: payload = {}

    # CRITICAL FIX: Ensure no newlines exist in the API key header
    headers = {'x-api-key': api_key.strip(), 'Content-Type': 'application/json'}
    items = []
    page = 1

    with requests.Session() as session:
        while True:
            url = f"{KISS_24_ENDPOINT}{endpoint}"
            response = session.post(url, headers=headers, params={'page': page}, json=payload, timeout=30)

            if not response.ok:
                if response.status_code == 400 and "Invalid Page Number" in response.text:
                    break
                else:
                    raise ValueError(f"API Error on {endpoint}. Status: {response.status_code}, Body: {response.text}")

            # CRITICAL FIX: Catch non-JSON HTML pages returned by WAFs
            try:
                data = response.json()
            except Exception:
                raise ValueError(
                    f"Invalid JSON returned from {url}. Status: {response.status_code}. Raw Body: {response.text[:300]}")

            items.extend(data.get('items', []))

            page_count = int(data.get('page_count', 1))
            if page >= page_count: break
            page += 1

    return items


def get_vuln_fields_map(vuln_uuids: list, api_key: str):
    """Fetches custom fields for vulnerabilities in chunks."""
    vuln_fields_map = {}
    if not vuln_uuids: return vuln_fields_map

    chunk_size = 20
    for i in range(0, len(vuln_uuids), chunk_size):
        chunk = vuln_uuids[i:i + chunk_size]
        fields_data = fetch_all_kiss24('fields', api_key, {"vulnerabilities": chunk})

        for item in fields_data:
            v_uuid = item.get('entity', {}).get('uuid')
            if v_uuid:
                if v_uuid not in vuln_fields_map:
                    vuln_fields_map[v_uuid] = []
                vuln_fields_map[v_uuid].append(item)

    return vuln_fields_map


def _is_field_populated(field_obj):
    val = field_obj.get('value')
    if val is None: return False
    if isinstance(val, list): return len(val) > 0
    if isinstance(val, str): return bool(val.strip())
    return True


def validate_kiss24_findings(vulns: list, vuln_fields_map: dict, report_type: int, api_key: str):
    """Validates contexts and MITRE ID fields, returning a list of violations."""
    invalid_findings = []
    context_cache = {}

    for vuln in vulns:
        vuln_uuid = vuln['uuid']
        reasons = []

        if report_type == 1:
            ctx_name = vuln.get('context', {}).get('name', '')
            if not ctx_name:
                vt_uuid = vuln.get('vulnerability_type', {}).get('uuid')
                if vt_uuid:
                    if vt_uuid not in context_cache:
                        ctxs = fetch_all_kiss24('provider/contexts', api_key,
                                                {"vulnerability_types": [vt_uuid]})
                        context_cache[vt_uuid] = ctxs[0].get('name', '') if ctxs else ''
                    ctx_name = context_cache[vt_uuid]

            if not ctx_name.startswith("[Adv Sim]"):
                reasons.append(f"Context '{ctx_name}' does not start with '[Adv Sim]'")

            mitre_filled = False
            for field in vuln_fields_map.get(vuln_uuid, []):
                if field.get('custom_field', {}).get('name') == 'MITRE ID':
                    if _is_field_populated(field): mitre_filled = True
                    break
            if not mitre_filled:
                reasons.append("MITRE ID custom field is empty or missing")

        created_at_str = vuln.get('created_at') or vuln.get('published_at', '')
        try:
            created_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            if created_date.tzinfo is None:
                created_date = created_date.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            created_date = datetime.now(timezone.utc)

        if created_date > CUTOFF_DATE:
            effort_filled = False
            for field in vuln_fields_map.get(vuln_uuid, []):
                if field.get('custom_field', {}).get('name') == 'Remediation Effort':
                    if _is_field_populated(field): effort_filled = True
                    break
            if not effort_filled:
                reasons.append("Remediation Effort custom field is missing (Required for new vulns)")

        if reasons:
            invalid_findings.append({
                "vuln_uuid": vuln_uuid,
                "reasons": reasons
            })

    return invalid_findings


def get_report_type_id(display_order: int) -> int:
    """Maps the service lane's display_order to the report type expected by osrgt_v3."""
    if display_order == 1:
        return 1  # Adversary Simulation
    elif display_order == 2:
        return 3  # White Box
    else:
        return 2  # Black/Grey Box

# ==========================================
# ---  6. HEALTH CHECK                   ---
# ==========================================
# Check User Api by using Server Health check
def verify_kiss24_api_key(test_key: str):
    """
    Hits the KISS24 health endpoint to verify if a specific API key is valid.
    Returns (True, "Ok") if valid, or (False, "Error Message") if invalid.
    """
    url = f"{KISS_24_ENDPOINT}health"

    # Using POST with an empty JSON body as required by KISS24
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"x-api-key": test_key, "Content-Type": "application/json"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req) as res:
            if res.status == 200:
                return True, "Ok"
    except urllib.error.HTTPError as e:
        if e.code == 403:
            return False, "Invalid API Key"
        return False, f"HTTP Error: {e.code}"
    except Exception as e:
        return False, str(e)

    return False, "Unknown Error"



