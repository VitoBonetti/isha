import json
import os
import urllib.request
from audit_logger import log_audit_event
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

