import os
import httpx
import json
import traceback
import google.auth.transport.requests
import google.oauth2.id_token
from utils.secret_manager import get_secret
from audit_logger import log_audit_event


def get_headers() -> dict:
    """Dynamically fetches and strips the Keep Secure 24 API key."""
    raw_key = get_secret(os.environ.get("KISS_24_API_KEY_NAME", ""))
    api_key = str(raw_key).strip() if raw_key else ""
    return {
        "accept": "*/*",
        "x-api-key": api_key,
        "Content-Type": "application/json"
    }


def _extract_str(data, key, default="") -> str:
    """Safely extracts a string from either a string or dict value."""
    val = data.get(key)
    if val is None:
        return default
    if isinstance(val, dict):
        return str(val.get("name") or val.get("title") or val.get("label") or default)
    return str(val)


async def get_vulns_from_test(client: httpx.AsyncClient, test_uuid: str) -> list:
    endpoint = (os.environ.get("KISS_24_ENDPOINT") or "").rstrip("/") + "/"
    url = f"{endpoint}vulnerabilities"
    response = await client.post(url, headers=get_headers(), json={"tests": [str(test_uuid)]}, timeout=30.0)
    response.raise_for_status()
    return response.json().get("items", [])


async def build_payload(test_uuid: str) -> dict:
    async with httpx.AsyncClient() as client:
        try:
            vulns = await get_vulns_from_test(client, test_uuid)
            all_mapped_vulns = []
            for vuln in vulns:
                vuln_uuid = _extract_str(vuln, "uuid")
                title_val = vuln.get("description") or vuln.get("name") or "No Title"
                all_mapped_vulns.append({
                    "uuid": vuln_uuid,
                    "title": str(title_val),
                    "severity": _extract_str(vuln, "severity"),
                    "details": _extract_str(vuln, "details"),
                    "state": _extract_str(vuln, "state"),
                    "attachments": vuln.get("attachments"),
                    "published_at": vuln.get("published_at"),
                    "created_by": vuln.get("created_by")
                })
            final_payload = {"vulnerabilities": all_mapped_vulns}
            print(f"[DEBUG] Outgoing Payload to Cloud Run ({len(all_mapped_vulns)} vulns):\n{json.dumps(final_payload, indent=2)}")
            return final_payload
        except Exception as e:
            error_msg = f"[ERROR] Payload building failed for test {test_uuid}: {e}\n{traceback.format_exc()}"
            print(error_msg)
            log_audit_event("SYSTEM", "SYSTEM", "VULN_ANALYSIS_PAYLOAD_ERROR", "ANALYSIS", str(test_uuid), error_msg)
            return {}


async def run_cloud_run_analysis(payload: dict) -> dict:
    cloud_run_url = (os.environ.get("CLOUD_RUN_ANALYSIS_URL") or "").rstrip("/")
    if not cloud_run_url:
        raise ValueError("CLOUD_RUN_ANALYSIS_URL environment variable is missing or unconfigured.")

    request = google.auth.transport.requests.Request()
    token = google.oauth2.id_token.fetch_id_token(request, cloud_run_url)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }

    # Extend timeout to 10 minutes (600s) for heavy LLM processing workloads
    timeout_config = httpx.Timeout(600.0, connect=15.0, read=600.0)

    try:
        async with httpx.AsyncClient(timeout=timeout_config) as client:
            response = await client.post(f"{cloud_run_url}/analyze", headers=headers, json=payload)
            if response.status_code == 422:
                print(f"[ERROR] Cloud Run 422 Validation Detail: {response.text}")
            response.raise_for_status()
            return response.json()
    except httpx.ReadTimeout:
        raise ValueError("The analysis service timed out waiting for the LLM response (>10 minutes). Try analyzing fewer vulnerabilities or check Cloud Run instance capacity.")