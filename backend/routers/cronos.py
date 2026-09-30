from fastapi import APIRouter, Request, Depends, HTTPException, BackgroundTasks, status
from jose import jwt
import os
import uuid
from routers.auth import get_google_public_keys
from websockets_manager import manager
from database import db_cursor_context
from audit_logger import log_audit_event
from system_services import asset_service, rag_service, kiss24_service, snow_service, dashboard_service

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
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Missing IAP JWT. Request bypassed IAP.")

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

@router.post(
    "/api-key-alerts",
    summary="Daily API Key Expiration Check"
)
async def gcp_trigger_api_key_alerts(
        request: Request,
        authenticated: bool = Depends(verify_cron_caller)
):
    """
    Trigger the daily API Key expiration routine.

    Called securely via Google Cloud Scheduler. Queries the database for all active API keys
    expiring within exactly 7 days (to trigger a warning notification) and keys expiring today
    (to trigger invalidation and error notifications).
    """
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


@router.post(
    "/servicenow-sync",
    summary="Weekly ServiceNow CMDB Sync"
)
def gcp_trigger_servicenow_sync(
        background_tasks: BackgroundTasks,
        authenticated: bool = Depends(verify_cron_caller)
):
    """
    Trigger the automated background sync with ServiceNow CMDB.

    Called securely via Google Cloud Scheduler. It immediately returns a success HTTP code to
    GCP and delegates the heavy CMDB processing script to a FastAPI BackgroundTask.
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


@router.post(
    "/rag-sync",
    summary="Daily RAG Knowledge Base Sync"
)
def gcp_trigger_rag_sync(
        background_tasks: BackgroundTasks,
        authenticated: bool = Depends(verify_cron_caller)
):
    """
    Trigger the daily Retrieval-Augmented Generation (RAG) Sync.

    Called securely via Google Cloud Scheduler. Triggers a background process that crawls
    Google Drive workspaces for newly uploaded scoping documents and rules, embedding them
    into the Vector Database for AI retrieval.
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


@router.post(
    "/kiss24-weekly-provision",
    summary="Weekly KISS24 Test Provisioning"
)
def gcp_trigger_kiss24_provision(
        background_tasks: BackgroundTasks,
        authenticated: bool = Depends(verify_cron_caller)
):
    """
    Trigger the Keep Secure 24 test auto-provisioning cycle.

    Called securely via Google Cloud Scheduler (typically Monday at 00:00 UTC). Looks for all
    platform tests scheduled for the current week that have met requirements but lack a KISS24 UUID,
    and automatically provisions them on the external platform.
    """
    background_tasks.add_task(
        kiss24_service.auto_provision_weekly_tests_background,
        "SYSTEM_CRON",
        "scheduler"
    )

    log_audit_event(
        user_id="SYSTEM_CRON",
        role="scheduler",
        action="CRON_KISS24_PROVISION_STARTED",
        resource_type="INTEGRATION",
        resource_id="kiss24",
        details="Weekly scheduled Keep Secure 24 test auto-provisioning initiated by Cloud Scheduler."
    )

    return {"message": "Weekly KISS24 auto-provisioning queued successfully."}


@router.post(
    "/servicenow-ritm-sync",
    summary="Daily ServiceNow RITM Sync"
)
def gcp_trigger_snow_ritm_sync(
        background_tasks: BackgroundTasks,
        authenticated: bool = Depends(verify_cron_caller)
):
    """
    Trigger the daily sync of active RITM tickets from ServiceNow.

    Called securely via Google Cloud Scheduler. Triggers an asynchronous task that fetches the
    most recent RITM data from the connected GCS bucket to ensure the local database stays in sync.
    """
    background_tasks.add_task(
        snow_service.process_ritm_sync_background,
        "SYSTEM_CRON",
        "scheduler"
    )

    log_audit_event(
        user_id="SYSTEM_CRON",
        role="scheduler",
        action="CRON_SNOW_RITM_SYNC_STARTED",
        resource_type="INTEGRATION",
        resource_id="servicenow_ritm",
        details="Daily scheduled database sync for RITM from ServiceNow initiated by Cloud Scheduler."
    )

    return {"message": "Daily sync for RITM from ServiceNow queued successfully."}


@router.post(
    "/snitcher-metrics",
    summary="Daily ServiceNow RITM Sync"
)
def gcp_trigger_snitch_metrics(
        background_tasks: BackgroundTasks,
        authenticated: bool = Depends(verify_cron_caller)
):
    """
    Trigger the weekly sync for the snitcher metrics.

    Called securely via Google Cloud Scheduler. Launch the Snitcher Metrics data pipeline.
    Initiates an asynchronous background worker that connects to the external Vulnerability Manager,
    fetches the full asset and history ledgers, calculates KPI movements via a Pandas dataframe,
    and commits the aggregated metrics to the PostgreSQL database.
    """
    background_tasks.add_task(
        dashboard_service.run_snitcher_sync,
        "SYSTEM_CRON",
        "scheduler"
    )

    log_audit_event(
        user_id="SYSTEM_CRON",
        role="scheduler",
        action="CRON_SNITCHER_STARTED",
        resource_type="SNITCHER",
        resource_id="snitcher_metrics",
        details="Weekly sync for the snitcher metrics initiated by Cloud Scheduler."
    )

    return {"message": "Weekly sync for the snitcher metrics queued successfully."}