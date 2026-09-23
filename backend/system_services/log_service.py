import io
import csv
from typing import List, Optional
from google.cloud import bigquery
from sqlalchemy.orm import Session
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from audit_logger import log_audit_event, get_bq_client, TABLE_REF
from models.users import Users
from utils.memory_cache import get_cached_json, set_cached_json


def get_recent_logs():
    client = get_bq_client()
    if not client:
        return []

    query = f"""
        SELECT timestamp, role, user_id, action, resource_type, resource_id, details 
        FROM `{TABLE_REF}`
        ORDER BY timestamp DESC LIMIT 100
    """
    try:
        results = client.query(query).result()
        logs = []
        for row in results:
            log_dict = dict(row)
            if log_dict.get("timestamp"):
                log_dict["timestamp"] = log_dict["timestamp"].isoformat()
            logs.append(log_dict)
        return logs
    except Exception as e:
        print(f"BigQuery Fetch Error: {e}")
        return []


def download_logs_csv(current_user: dict):
    client = get_bq_client()
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery not configured.")

    query = f"SELECT timestamp, role, user_id, action, resource_type, resource_id, details FROM `{TABLE_REF}` ORDER BY timestamp ASC"

    try:
        results = client.query(query).result()
        output = io.StringIO()
        writer = csv.writer(output)

        # Write CSV Headers
        writer.writerow(["Timestamp", "Role", "User ID", "Action", "Resource Type", "Resource ID", "Details"])

        # Write Data
        for row in results:
            ts = row.timestamp.isoformat() if row.timestamp else "UNKNOWN"
            writer.writerow([ts, row.role, row.user_id, row.action, row.resource_type, row.resource_id, row.details])

        output.seek(0)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="LOGS_DOWNLOADED",
            resource_type="LOGS",
            resource_id="N/A",
            details="Downloaded complete CSV archive."
        )
        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="security_audit_logs.csv"'}
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV: {e}")


def clear_all_logs(current_user: dict):
    client = get_bq_client()
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery not configured.")

    try:
        client.query(f"TRUNCATE TABLE `{TABLE_REF}`").result()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="LOGS_DELETED",
            resource_type="LOGS",
            resource_id="N/A",
            details="Truncated BigQuery audit logs."
        )
        return {"message": "All BigQuery logs cleared."}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear logs: {e}")


def get_log_filters(db: Session):
    """Fetches unique resources, actions, and maps BQ users to DB users (cached for 1 hour)."""
    cache_key = "bq_audit_log_filters"
    cached_data = get_cached_json(cache_key)
    if cached_data:
        return cached_data

    client = get_bq_client()
    if not client:
        return {"resource_types": [], "actions": {}, "users": []}

    # 1. Fetch Distinct Values from BigQuery
    query = f"""
        SELECT 
            ARRAY_AGG(DISTINCT resource_type IGNORE NULLS) as resources,
            ARRAY_AGG(DISTINCT action IGNORE NULLS) as actions,
            ARRAY_AGG(DISTINCT user_id IGNORE NULLS) as users
        FROM `{TABLE_REF}`
    """
    try:
        result = list(client.query(query).result())[0]
        raw_resources = result.resources or []
        raw_actions = result.actions or []
        raw_users = result.users or []

        # 2. Map Actions to Resource Types (Querying distinct pairs)
        pairs_query = f"SELECT DISTINCT resource_type, action FROM `{TABLE_REF}` WHERE resource_type IS NOT NULL"
        pairs_result = client.query(pairs_query).result()
        actions_by_resource = {}
        for row in pairs_result:
            r_type = row.resource_type
            act = row.action
            if r_type not in actions_by_resource:
                actions_by_resource[r_type] = []
            actions_by_resource[r_type].append(act)

        # 3. Cross-reference Users with PostgreSQL to handle UUID + Email duplicates
        db_users = db.query(Users.id, Users.email).all()
        user_mapping = {str(u.id): u.email for u in db_users}
        reverse_email_mapping = {u.email: str(u.id) for u in db_users}

        grouped_users = {}
        for bq_user in raw_users:
            # Determine the logical owner
            if bq_user in user_mapping:
                owner_email = user_mapping[bq_user]
            elif bq_user in reverse_email_mapping:
                owner_email = bq_user
            else:
                owner_email = bq_user  # Fallback for SYSTEM, UNAUTHENTICATED, etc.

            if owner_email not in grouped_users:
                grouped_users[owner_email] = {"label": owner_email, "values": []}

            grouped_users[owner_email]["values"].append(bq_user)

        formatted_users = list(grouped_users.values())

        final_data = {
            "resource_types": sorted(raw_resources),
            "actions_by_resource": actions_by_resource,
            "users": sorted(formatted_users, key=lambda x: x["label"])
        }

        # Cache for 1 hour (3600 seconds is handled by memory_cache TTL)
        set_cached_json(cache_key, final_data)
        return final_data

    except Exception as e:
        print(f"Failed to fetch BQ filters: {e}")
        return {"resource_types": [], "actions": {}, "users": []}


def search_audit_logs(req, current_user: dict):
    """Executes a highly parameterized, paginated search against BigQuery."""
    client = get_bq_client()
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery not configured.")

    where_clauses = ["1=1"]
    query_params = []

    # 1. Apply Standard Filters
    if req.resource_type:
        where_clauses.append("resource_type = @resource_type")
        query_params.append(bigquery.ScalarQueryParameter("resource_type", "STRING", req.resource_type))

    if req.action:
        where_clauses.append("action = @action")
        query_params.append(bigquery.ScalarQueryParameter("action", "STRING", req.action))

    if req.user_id_group and len(req.user_id_group) > 0:
        where_clauses.append("user_id IN UNNEST(@user_id_group)")
        query_params.append(bigquery.ArrayQueryParameter("user_id_group", "STRING", req.user_id_group))

    # 2. Apply Time Filters (Relative vs Specific)
    if req.time_preset == "24h":
        where_clauses.append("timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)")
    elif req.time_preset == "7d":
        where_clauses.append("timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)")
    elif req.time_preset == "30d":
        where_clauses.append("timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)")
    else:
        if req.start_date:
            where_clauses.append("timestamp >= @start_date")
            query_params.append(bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", req.start_date))
        if req.end_date:
            where_clauses.append("timestamp <= @end_date")
            query_params.append(bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", req.end_date))

    where_str = " AND ".join(where_clauses)

    # 3. Calculate Pagination Metrics
    offset = (req.page - 1) * req.limit

    count_query = f"SELECT COUNT(*) as total FROM `{TABLE_REF}` WHERE {where_str}"
    data_query = f"""
        SELECT timestamp, role, user_id, action, resource_type, resource_id, details 
        FROM `{TABLE_REF}` 
        WHERE {where_str} 
        ORDER BY timestamp DESC 
        LIMIT @limit OFFSET @offset
    """

    query_params.extend([
        bigquery.ScalarQueryParameter("limit", "INT64", req.limit),
        bigquery.ScalarQueryParameter("offset", "INT64", offset)
    ])

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    try:
        # Execute Total Count
        count_result = list(client.query(count_query, job_config=job_config).result())
        total_count = count_result[0].total if count_result else 0

        # Execute Data Query
        results = client.query(data_query, job_config=job_config).result()
        logs = []
        for row in results:
            log_dict = dict(row)
            if log_dict.get("timestamp"):
                log_dict["timestamp"] = log_dict["timestamp"].isoformat()
            logs.append(log_dict)

        return {
            "items": logs,
            "total_count": total_count,
            "page": req.page,
            "limit": req.limit,
            "total_pages": (total_count + req.limit - 1) // req.limit
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"BigQuery Search Error: {e}")


def download_search_logs_csv(req, current_user: dict):
    """Executes the advanced search and streams all matching results as a CSV."""
    client = get_bq_client()
    if not client:
        raise HTTPException(status_code=500, detail="BigQuery not configured.")

    where_clauses = ["1=1"]
    query_params = []

    # 1. Apply Standard Filters
    if req.resource_type:
        where_clauses.append("resource_type = @resource_type")
        query_params.append(bigquery.ScalarQueryParameter("resource_type", "STRING", req.resource_type))

    if req.action:
        where_clauses.append("action = @action")
        query_params.append(bigquery.ScalarQueryParameter("action", "STRING", req.action))

    if req.user_id_group and len(req.user_id_group) > 0:
        where_clauses.append("user_id IN UNNEST(@user_id_group)")
        query_params.append(bigquery.ArrayQueryParameter("user_id_group", "STRING", req.user_id_group))

    # 2. Apply Time Filters
    if req.time_preset == "24h":
        where_clauses.append("timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)")
    elif req.time_preset == "7d":
        where_clauses.append("timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 7 DAY)")
    elif req.time_preset == "30d":
        where_clauses.append("timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 30 DAY)")
    else:
        if req.start_date:
            where_clauses.append("timestamp >= @start_date")
            query_params.append(bigquery.ScalarQueryParameter("start_date", "TIMESTAMP", req.start_date))
        if req.end_date:
            where_clauses.append("timestamp <= @end_date")
            query_params.append(bigquery.ScalarQueryParameter("end_date", "TIMESTAMP", req.end_date))

    where_str = " AND ".join(where_clauses)

    # 3. Query all data without limits (ordering chronologically for a CSV)
    data_query = f"""
        SELECT timestamp, role, user_id, action, resource_type, resource_id, details 
        FROM `{TABLE_REF}` 
        WHERE {where_str} 
        ORDER BY timestamp ASC
    """

    job_config = bigquery.QueryJobConfig(query_parameters=query_params)

    try:
        results = client.query(data_query, job_config=job_config).result()

        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Timestamp", "Role", "User ID", "Action", "Resource Type", "Resource ID", "Details"])

        for row in results:
            ts = row.timestamp.isoformat() if row.timestamp else "UNKNOWN"
            writer.writerow([ts, row.role, row.user_id, row.action, row.resource_type, row.resource_id, row.details])

        output.seek(0)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="LOGS_SEARCH_DOWNLOADED",
            resource_type="LOGS",
            resource_id="N/A",
            details="Downloaded filtered CSV archive from Live Search."
        )

        return StreamingResponse(
            output,
            media_type="text/csv",
            headers={"Content-Disposition": 'attachment; filename="filtered_audit_logs.csv"'}
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to generate CSV: {e}")