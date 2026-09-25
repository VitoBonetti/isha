from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks, status
from jose import jwt
import os
import uuid
from routers.auth import get_google_public_keys
from websockets_manager import manager
from database import db_cursor_context
from audit_logger import log_audit_event
from system_services import asset_service, rag_service

router = APIRouter(prefix="/api/cronos", tags=["Google CronJobs"])


# ---------------------------------------------------------
# --- SECURITY DEPENDENCY FOR CRON ENDPOINTS ---
# ---------------------------------------------------------

def verify_cron_caller(request: Request) -> bool:
    """
    Ensures the caller is strictly Google Cloud Scheduler passing through IAP
    using the authorized Service Account.
    """
    if os.environ.get("ENV") != "local":
        iap_jwt = request.headers.get("x-goog-iap-jwt-assertion")
        if not iap_jwt:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing IAP JWT. Request bypassed IAP.")

        try:
            kid = jwt.get_unverified_header(iap_jwt).get("kid")
            public_keys = get_google_public_keys()
            public_key = public_keys.get(kid)
            if not public_key:
                raise ValueError("Invalid IAP Token Header Key ID")

            payload = jwt.decode(
                iap_jwt,
                public_key,
                algorithms=["ES256"],
                audience=os.environ.get("IAP_AUDIENCE")
            )

            email = payload.get("email")
            expected_sa = os.environ.get("IAM_SA_EMAIL")

            # Verify the email matches the authorized system Service Account
            if email != f"accounts.google.com:{expected_sa}" and email != expected_sa:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"Unauthorized caller: {email}")

        except Exception as e:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"IAP Validation Failed: {str(e)}")

    return True


# ---------------------------------------------------------
# --- API KEY EXPIRATION SCHEDULER LOGIC ---
# ---------------------------------------------------------

async def run_api_key_expiration_check():
    with db_cursor_context() as cursor:
        if not cursor:
            return

        cursor.execute("""
            SELECT ak.id, ak.name, ak.user_id 
            FROM api_keys ak
            WHERE ak.is_active = TRUE 
              AND DATE(ak.expires_at) = (CURRENT_DATE AT TIME ZONE 'UTC') + INTERVAL '7 days'
        """)
        expiring_soon = cursor.fetchall()

        for key_id, key_name, user_id in expiring_soon:
            notif_id = str(uuid.uuid4())
            msg = f"Your API Key '{key_name}' expires in exactly 7 days. Please generate a new one to prevent service interruption."
            cursor.execute("""
                INSERT INTO notifications (id, user_id, message, type, created_at)
                VALUES (%s, %s, %s, 'WARNING', CURRENT_TIMESTAMP)
            """, (notif_id, str(user_id), msg))

        cursor.execute("""
            SELECT ak.id, ak.name, ak.user_id 
            FROM api_keys ak
            WHERE ak.is_active = TRUE 
              AND DATE(ak.expires_at) <= DATE(CURRENT_TIMESTAMP AT TIME ZONE 'UTC')
        """)
        expired_today = cursor.fetchall()

        for key_id, key_name, user_id in expired_today:
            notif_id = str(uuid.uuid4())
            msg = f"Your API Key '{key_name}' has expired and is no longer valid."
            cursor.execute("""
                INSERT INTO notifications (id, user_id, message, type, created_at)
                VALUES (%s, %s, %s, 'ERROR', CURRENT_TIMESTAMP)
            """, (notif_id, str(user_id), msg))

            cursor.execute("UPDATE api_keys SET is_active = FALSE WHERE id = %s", (key_id,))

        cursor.connection.commit()

        if expiring_soon or expired_today:
            await manager.broadcast('{"action": "REFRESH_BOARD"}')


# ---------------------------------------------------------
# --- GOOGLE SCHEDULER ENDPOINTS ---
# ---------------------------------------------------------

@router.post("/api-key-alerts", summary="GCP Scheduler trigger for daily API Key expiration alerts")
async def gcp_trigger_api_key_alerts(
    request: Request,
    authenticated: bool = Depends(verify_cron_caller)
):
    print("🔔 GCP Scheduler triggered daily API key expiration check.")
    await run_api_key_expiration_check()

    log_audit_event(
        user_id="SYSTEM_CRON",
        role="scheduler",
        action="CRON_API_KEY_ALERT",
        resource_type="SYSTEM",
        resource_id="api_key_check",
        details="Successfully executed daily API key expiration check via IAP OIDC."
    )

    return {"message": "API key expiration check executed successfully."}


@router.post("/servicenow-sync", summary="GCP Scheduler trigger for weekly ServiceNow CMDB sync")
def gcp_trigger_servicenow_sync(
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_cron_caller)
):
    """
    Weekly background sync with ServiceNow CMDB.
    Runs asynchronously using FastAPI BackgroundTasks.
    """
    background_tasks.add_task(
        asset_service.full_background_sync_wrapper,
        "SYSTEM_CRON",
        "scheduler"
    )

    log_audit_event(
        user_id="SYSTEM_CRON",
        role="scheduler",
        action="CRON_SNOW_SYNC_STARTED",
        resource_type="INTEGRATION",
        resource_id="servicenow_cmdb",
        details="Weekly scheduled ServiceNow CMDB sync initiated by Cloud Scheduler."
    )

    return {"message": "Weekly ServiceNow sync queued successfully."}


@router.post("/rag-sync", summary="GCP Scheduler trigger for daily RAG knowledge base sync")
def gcp_trigger_rag_sync(
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_cron_caller)
):
    """
    Daily background sync for RAG Knowledge Base and Test Documents.
    Runs asynchronously at 05:00 UTC.
    """
    background_tasks.add_task(
        rag_service.sync_all_active_tests_background,
        "SYSTEM_CRON",
        "scheduler"
    )

    log_audit_event(
        user_id="SYSTEM_CRON",
        role="scheduler",
        action="CRON_RAG_SYNC_STARTED",
        resource_type="INTEGRATION",
        resource_id="rag_knowledge_base",
        details="Daily scheduled RAG sync initiated by Cloud Scheduler."
    )

    return {"message": "Daily RAG sync queued successfully."}