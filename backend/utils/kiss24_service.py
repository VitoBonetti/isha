import json
import os
import urllib.request
import urllib.error
import re
from utils.secret_manager import get_secret


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
def create_test(ouuid: str, body: dict):
    endpoint = f"provider/tests/{ouuid}/create"
    url = f"{KISS_24_ENDPOINT}{endpoint}"
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"x-api-key": api_key(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req) as res:
        if res.status == 200:
            response_data =  json.loads(res.read())
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


# Add Service Now ID to Assets
def add_snowid_to_kiss24asset(map: dict):
    counter = 0
    for key, value in map.items():
        url = f"{KISS_24_ENDPOINT}assets/{key}/edit"
        print(url)
        body_text = str(value)
        print(body_text)
        body = {
            "custom_fields": [
                {
                    "parent": "Service Now ID",
                    "text": body_text,
                }
            ]
        }

        req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers={"x-api-key": api_key(), "Content-Type": "application/json"}, method="PATCH")
        try:
            with urllib.request.urlopen(req) as res:
                if res.status == 200:
                    raw_data = res.read()
                    try:
                        response_data = json.loads(raw_data.decode('utf-8'))
                        print(response_data)
                    except json.JSONDecodeError:
                        print(f"Update successful, but received non-JSON response: {raw_data}")
                    counter += 1
        except urllib.error.URLError as e:
            # Added basic error handling so one failed asset doesn't stop the whole loop
            print(f"Request failed for {key}: {e}")

        print(f"{counter} / {len(map)}")