from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends, HTTPException, APIRouter
from jose import jwt
import os
import uuid
from routers.auth import get_google_public_keys
from websockets_manager import manager
from database import get_db_cursor, db_cursor_context
from audit_logger import log_audit_event


router = APIRouter(prefix="/api/cronos", tags=["Google CronJobs"])


# ---------------------------------------------------------
# --- API KEY EXPIRATION SCHEDULER & LOGIC ---
# ---------------------------------------------------------

async def run_api_key_expiration_check():
    """
    Core logic: Scans for expiring/expired API keys and issues notifications.
    """
    with db_cursor_context() as cursor:
        if not cursor:
            return

        # 1. Warn users whose keys expire in exactly 7 days
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

        # 2. Alert users whose keys expired today & deactivate them
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

            # Force it inactive
            cursor.execute("UPDATE api_keys SET is_active = FALSE WHERE id = %s", (key_id,))

        cursor.connection.commit()

        # If any alerts were generated, broadcast to frontend
        if expiring_soon or expired_today:
            await manager.broadcast('{"action": "REFRESH_BOARD"}')



# --- GOOGLE SCHEDULER ENDPOINTS ---
@router.post("/api-key-alerts", summary="GCP Scheduler trigger for daily API Key expiration alerts")
async def gcp_trigger_api_key_alerts(request: Request):
    if os.environ.get("ENV") != "local":
        iap_jwt = request.headers.get("x-goog-iap-jwt-assertion")
        if not iap_jwt:
            raise HTTPException(status_code=401, detail="Missing IAP JWT. Request bypassed IAP.")

        try:
            # Reusing your existing websocket IAP validation logic
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

            # Verify the request is coming strictly from your allowed Service Account
            email = payload.get("email")
            expected_sa = os.environ.get("IAM_SA_EMAIL")

            # IAP prefixes service account emails with "accounts.google.com:"
            if email != f"accounts.google.com:{expected_sa}" and email != expected_sa:
                raise HTTPException(status_code=403, detail=f"Unauthorized Service Account: {email}")

        except Exception as e:
            raise HTTPException(status_code=403, detail=f"IAP Validation Failed: {str(e)}")

    # Execute the core logic
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