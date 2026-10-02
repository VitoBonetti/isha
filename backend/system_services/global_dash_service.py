# system_services/global_dash_service.py
import os
from datetime import datetime, date
from fastapi import HTTPException
from utils.memory_cache import get_cached_json, set_cached_json
from audit_logger import get_bq_client


def _serialize_bq_row(row: dict) -> dict:
    """Safely converts BQ Date/Datetime objects to ISO strings for React."""
    serialized = {}
    for key, value in row.items():
        # This catches all your specific TIMESTAMP and DATE columns dynamically
        if isinstance(value, (datetime, date)):
            serialized[key] = value.isoformat()
        else:
            serialized[key] = value
    return serialized


def fetch_and_cache_watchtower_data():
    client = get_bq_client()
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery client failed to initialize.")

    table_ref = os.environ.get('WATCHTOWER_VULNS_VULNERABILITY_SCOPE')
    if not table_ref:
        raise HTTPException(status_code=500, detail="WATCHTOWER_VULNS_VULNERABILITY is missing in env.")

    query = f"SELECT * FROM `{table_ref}`"

    try:
        results = client.query(query).result()
        data = [_serialize_bq_row(dict(row)) for row in results]
        set_cached_json("watchtower_vulns_global", data, ttl=14400)
        return data
    except Exception as e:
        # DO NOT SWALLOW THE ERROR - throw it so we can see exactly what's wrong
        raise HTTPException(status_code=500, detail=f"BigQuery Crash: {str(e)}")


def get_filtered_dashboard_data(access_profile: dict):
    # 1. Fetch from RAM Cache, fallback to BigQuery if cache expired/empty
    data = get_cached_json("watchtower_vulns_global")
    if not data:
        data = fetch_and_cache_watchtower_data()

    # 2. Return everything if they are an internal team member
    if access_profile.get("is_global"):
        return data

    # 3. Filter down to only authorized OpCos for Stakeholders
    allowed = set(access_profile.get("allowed_opcos", []))

    # Python list comprehension filters 7k rows in a fraction of a millisecond
    filtered_data = [
        row for row in data
        if row.get("OpCo") and str(row.get("OpCo")).upper().strip() in allowed
    ]

    return filtered_data


def get_dashboard_summary_and_items(access_profile: dict, opco_filter: str = None, severity_filter: str = None,
                                    state_filter: str = None):
    data = get_filtered_dashboard_data(access_profile)

    # Optional sub-filtering
    if opco_filter and opco_filter != "ALL":
        data = [r for r in data if str(r.get("OpCo")).upper() == opco_filter.upper()]
    if severity_filter and severity_filter != "ALL":
        data = [r for r in data if str(r.get("Severity")).lower() == severity_filter.lower()]
    if state_filter and state_filter != "ALL":
        data = [r for r in data if str(r.get("State")).lower() == state_filter.lower()]

    # Server-side aggregations (Calculated in Python in ~2 milliseconds)
    summary = {
        "total": len(data),
        "critical": sum(1 for r in data if str(r.get("Severity")).lower() == "critical"),
        "high": sum(1 for r in data if str(r.get("Severity")).lower() == "high"),
        "medium": sum(1 for r in data if str(r.get("Severity")).lower() == "medium"),
        "low": sum(1 for r in data if str(r.get("Severity")).lower() == "low"),
        "info": sum(1 for r in data if str(r.get("Severity")).lower() == "info"),
        "policy_overdue": sum(1 for r in data if r.get("Policy_Overdue") is True),
        "kpi_overdue": sum(1 for r in data if r.get("KPI_Overdue") is True),
        "open": sum(1 for r in data if str(r.get("State")).lower() in ["open", "new"]),
        "validating": sum(1 for r in data if str(r.get("State")).lower() == "validating"),
        "parked": sum(1 for r in data if str(r.get("State")).lower() == "parked"),
        "closed": sum(1 for r in data if str(r.get("State")).lower() == "closed"),
    }

    # Available OpCos for dropdown selection
    available_opcos = sorted(list({str(r.get("OpCo")).upper() for r in data if r.get("OpCo")}))

    return {
        "summary": summary,
        "available_opcos": available_opcos,
        "items": data[:200]  # Cap table items to 200 for instant UI rendering
    }