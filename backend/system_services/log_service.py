import io
import csv
from fastapi import HTTPException
from fastapi.responses import StreamingResponse
from audit_logger import log_audit_event, get_bq_client, TABLE_REF


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