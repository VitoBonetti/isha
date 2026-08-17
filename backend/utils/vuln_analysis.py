import os
import httpx
import json
import google.auth.transport.requests
import google.oauth2.id_token
from utils.secret_manager import get_secret

KISS_24_API_KEY = get_secret(os.environ.get("KISS_24_API_KEY_NAME"))
KISS_24_ENDPOINT = os.environ.get("KISS_24_ENDPOINT")
CLOUD_RUN_URL = os.environ.get("CLOUD_RUN_ANALYSIS_URL")

HEADERS = {
    "accept": "*/*",
    "x-api-key": KISS_24_API_KEY,
    "Content-Type": "application/json"
}


def _extract_str(data, key, default=""):
    """Safely extracts a string from either a string or dict value."""
    val = data.get(key)
    if val is None:
        return default
    if isinstance(val, dict):
        return str(val.get("name") or val.get("title") or val.get("label") or default)
    return str(val)


async def get_vulns_from_test(client, test_uuid):
    url = f"{KISS_24_ENDPOINT}vulnerabilities"
    response = await client.post(url, headers=HEADERS, json={"tests": [test_uuid]}, timeout=30.0)
    response.raise_for_status()
    return response.json().get("items", [])


async def build_payload(test_uuid):
    async with httpx.AsyncClient() as client:
        try:
            vulns = await get_vulns_from_test(client, test_uuid)
            all_mapped_vulns = []

            for vuln in vulns:
                vuln_uuid = _extract_str(vuln, "uuid")

                # Extract title safely from description, title, or name
                title_val = vuln.get("description")

                all_mapped_vulns.append({
                    "uuid": vuln_uuid,
                    "title": str(title_val),
                    "severity": _extract_str(vuln, "severity"),
                    "details": _extract_str(vuln, "details"),
                    "state": _extract_str(vuln, "state"),
                    "attachments": vuln.get("attachments"),
                    "published_at": vuln.get("published_at"),  # Can be null
                    "created_by": vuln.get("created_by")
                })

            final_payload = {"vulnerabilities": all_mapped_vulns}

            # Print exact JSON payload to backend logs for debugging
            print(f"[DEBUG] Outgoing Payload to Cloud Run:\n{json.dumps(final_payload, indent=2)}")

            return final_payload
        except Exception as e:
            print(f"[ERROR] Payload building failed: {e}")
            return {}


async def run_cloud_run_analysis(payload):
    request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(request, CLOUD_RUN_URL)

    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    async with httpx.AsyncClient() as client:
        response = await client.post(f"{CLOUD_RUN_URL}/analyze", headers=headers, json=payload, timeout=180.0)

        # Log response details if validation fails
        if response.status_code == 422:
            print(f"[ERROR] Cloud Run 422 Validation Detail: {response.text}")

        response.raise_for_status()
        return response.json()