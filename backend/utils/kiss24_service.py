import json
import os
import urllib.request
import urllib.error
import re
from utils.secret_manager import get_secret
from audit_logger import log_audit_event


KISS_24_ENDPOINT = os.environ.get("KISS_24_ENDPOINT")
KISS_24_API_KEY_NAME = os.environ.get("KISS_24_API_KEY_NAME")

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