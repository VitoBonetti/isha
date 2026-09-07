import os
from dotenv import load_dotenv
import httpx
import hashlib
import secrets
import uuid
import asyncio
from datetime import datetime, time, timedelta, timezone
from fastapi.security import APIKeyHeader
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status, BackgroundTasks
from jose import jwt, JWTError
from database import get_db_cursor, db_cursor_context
from websockets_manager import manager
from schema import ApiKeyCreate
from audit_logger import log_audit_event

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

IAP_AUDIENCE = os.environ.get("IAP_AUDIENCE")
ALGORITHM = "HS256"
# Global cache for Google IAP Public Keys
IAP_PUBLIC_KEYS = {}
IAP_KEYS_LAST_REFRESH = 0


def get_google_public_keys() -> dict:
    """Fetches and caches Google IAP public keys safely using httpx."""
    global IAP_PUBLIC_KEYS, IAP_KEYS_LAST_REFRESH
    import time

    # Refresh if empty or if 1 hour has passed
    if not IAP_PUBLIC_KEYS or (time.time() - IAP_KEYS_LAST_REFRESH > 3600):
        try:
            # Using synchronous client context manager for the dependency flow
            with httpx.Client() as client:
                resp = client.get("https://www.gstatic.com/iap/verify/public_key")
                if resp.status_code == 200:
                    IAP_PUBLIC_KEYS = resp.json()
                    IAP_KEYS_LAST_REFRESH = time.time()
                else:
                    # Fallback to current cache if Google is down or rate-limiting
                    if not IAP_PUBLIC_KEYS:
                        raise HTTPException(status_code=500, detail="Failed to fetch IAP public keys from Google")
        except Exception as e:
            if not IAP_PUBLIC_KEYS:
                raise HTTPException(status_code=500, detail=f"IAP Key Fetch Error: {str(e)}")

    return IAP_PUBLIC_KEYS


# --- 1. SECURITY MIDDLEWARE (DUAL-AUTH) ---
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(api_key: str) -> str:
    """Hashes the API key using SHA-256 for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_current_user(request: Request, api_key: str = Depends(api_key_header), cursor=Depends(get_db_cursor)):
    # METHOD A: API KEY AUTHENTICATION (For Scripts & Integrations)
    if api_key:
        hashed = hash_api_key(api_key)
        # Added expiration enforcement to the WHERE clause
        cursor.execute("""
                SELECT u.id, u.email, u.name, u.role, u.location_id, u.service_lane_id
                FROM users u
                JOIN api_keys ak ON u.id = ak.user_id
                WHERE ak.hashed_key = %s 
                  AND ak.is_active = TRUE 
                  AND (ak.expires_at IS NULL OR ak.expires_at > CURRENT_TIMESTAMP)
            """, (hashed,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid, revoked, or expired API Key")

        return {
            "id": user[0], "email": user[1], "name": user[2], "role": user[3], "location_id": user[4],
            "service_lane_id": user[5]
        }

    # METHOD B: GOOGLE IAP HEADER AUTHENTICATION (For the React Frontend)
    iap_jwt = request.headers.get("X-Goog-IAP-JWT-Assertion")

    if not iap_jwt:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Request must go through the IAP Load Balancer or provide X-API-Key."
        )

    try:
        # 1. Grab the key ID (kid) without verifying the signature yet
        unverified_header = jwt.get_unverified_header(iap_jwt)
        kid = unverified_header.get("kid")
        # 2. Get our cached public keys and pull the specific matching key
        public_keys = get_google_public_keys()
        public_key = public_keys.get(kid)

        if not public_key:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid IAP Token Header Key ID")

        # 3. Decode and cryptographically verify the JWT token
        # This checks expiry, signature validity, and ensures the token belongs to your project
        payload = jwt.decode(
            iap_jwt,
            public_key,
            algorithms=["ES256"],  # Google IAP tokens strictly use ES256
            audience=IAP_AUDIENCE
        )

        email: str = payload.get("email")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail="Invalid identity layout in IAP payload")

    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    cursor.execute("SELECT id, email, name, role, location_id, service_lane_id FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail="User account is authenticated via Google, but has not been invited to this system.")

    return {
        "id": user[0],
        "email": user[1],
        "name": user[2],
        "role": user[3],
        "location_id": user[4],
        "service_lane_id": user[5]
    }


def require_admin(current_user: dict = Depends(get_current_user)):
    """Strictly for Global Admins."""
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    return current_user


def require_write_access(current_user: dict = Depends(get_current_user)):
    """Blocks read-only users, but allows Pentester, Maintainer, and Admin."""
    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Read-only account cannot perform this action.")
    return current_user


def verify_lane_access(current_user: dict, target_lane_id: str):
    """
    Helper function to call INSIDE endpoints (e.g., PUT /tests/{id})
    to ensure Maintainers only edit their own lane's resources.
    """
    if current_user.get('role') == 'admin':
        return True

    if current_user.get('role') == 'maintainer':
        if str(current_user.get('service_lane_id')) == str(target_lane_id):
            return True
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maintainers can only modify resources assigned to their specific Service Lane."
        )

    # If they are a Pentester or Read Only, they shouldn't be using admin endpoints anyway,
    # but we block them here just in case.
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient privileges.")


def require_maintainer_or_admin(current_user: dict = Depends(get_current_user)):
    """Allows Global Admins and Maintainers, but blocks Pentesters and Read-Only users."""
    if current_user.get('role') not in ['admin', 'maintainer']:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Maintainer or Admin privileges required."
        )
    return current_user


@router.post("/logout")
def logout(background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    """
    Log the user out of the current session
    1. We still want to announce the user left via websockets
    2. send the required Google IAP logout URL back to the React frontend.
    """
    # 1. We still want to announce the user left via websockets
    background_tasks.add_task(
        manager.broadcast,
        f'{{"action": "USER_LEFT", "email": "{current_user["email"]}"}}'
    )

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="LOGOUT",
        resource_type="USER",
        resource_id=str(current_user["id"]),
        details=f"{current_user['id']} has logout."
    )

    #  send the required Google IAP logout URL back to the React frontend.
    return {
        "message": "Successfully logged out of backend.",
        "iap_logout_url": "/_gcp_iap/clear_login_cookie"
    }


# --- 2. SESSION & API KEY MANAGEMENT ---
@router.get("/keys")
def list_api_keys(global_view: bool = False, current_user: dict = Depends(get_current_user),
                  cursor=Depends(get_db_cursor)):
    """
    Lists API keys. Admins see all keys, regular users see only their own.
    """
    if global_view and current_user['role'] == 'admin':
        # Added ak.expires_at
        cursor.execute("""
            SELECT ak.id, ak.name as key_name, ak.prefix, ak.created_at, ak.expires_at, u.name as owner_name, u.email as owner_email
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            ORDER BY ak.created_at DESC
        """)
    else:
        # Added expires_at
        cursor.execute("""
            SELECT id, name as key_name, prefix, created_at, expires_at, NULL as owner_name, NULL as owner_email
            FROM api_keys 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (str(current_user['id']),))

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/keys")
def create_api_key(req: ApiKeyCreate, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Generates a new API Key with a 90-day expiration.
    """
    raw_key = "isha_" + secrets.token_urlsafe(32)
    prefix = raw_key[:10]
    hashed = hash_api_key(raw_key)
    new_id = str(uuid.uuid4())

    # Set TTL to 90 days from right now
    expires_at = datetime.now(timezone.utc) + timedelta(days=90)

    cursor.execute(
        """INSERT INTO api_keys (id, user_id, name, prefix, hashed_key, created_at, expires_at, is_active) 
           VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, %s, TRUE)""",
        (new_id, str(current_user['id']), req.name, prefix, hashed, expires_at)
    )
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="CREATE_API_KEY",
        resource_type="USER",
        resource_id=str(new_id),
        details=f"{current_user['id']} created a new API Key expiring on {expires_at.strftime('%Y-%m-%d')}."
    )

    return {
        "id": new_id,
        "name": req.name,
        "prefix": prefix,
        "raw_key": raw_key,
        "expires_at": expires_at.isoformat(),
        "message": "Store this key safely! It will not be shown again."
    }


@router.delete("/keys/{key_id}")
def revoke_api_key(key_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Deletes an API key. Admins can delete any key, users can only delete their own.
    """
    if current_user['role'] == 'admin':
        cursor.execute("DELETE FROM api_keys WHERE id = %s", (key_id,))
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="DELETE_API_KEY",
            resource_type="USER",
            resource_id=f"User ID: {current_user['id']} - API Key ID: {key_id} ",
            details=f"{current_user['role']} with ID: {current_user['id']} delete API Key ID: {key_id}."
        )
    else:
        cursor.execute("DELETE FROM api_keys WHERE id = %s AND user_id = %s", (key_id, str(current_user['id'])))
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="DELETE_ALL_API_KEY",
            resource_type="USER",
            resource_id=f"User ID: {current_user['id']} - API Key ID: {key_id} ",
            details=f"{current_user['role']} with ID: {current_user['id']} delete all API Key with ID: {key_id}."
        )
    cursor.connection.commit()

    return {"message": "API Key successfully revoked."}


# --- CRON JOB ENDPOINT FOR ALERTS ---
@router.post("/system/cron/api-key-alerts", summary="Trigger daily API Key expiration alerts")
def trigger_api_key_alerts(background_tasks: BackgroundTasks, cursor=Depends(get_db_cursor)):
    """
    This endpoint should be hit once a day by GCP Cloud Scheduler or a local cron job.
    It issues warnings for keys expiring in 7 days, and final notices for keys expiring today.
    """
    # 1. Warn users whose keys expire in exactly 7 days
    cursor.execute("""
        SELECT ak.id, ak.name, ak.user_id 
        FROM api_keys ak
        WHERE ak.is_active = TRUE 
          AND DATE(ak.expires_at) = CURRENT_DATE + INTERVAL '7 days'
    """)
    expiring_soon = cursor.fetchall()

    for key_id, key_name, user_id in expiring_soon:
        notif_id = str(uuid.uuid4())
        msg = f"Your API Key '{key_name}' expires in exactly 7 days. Please generate a new one to prevent service interruption."
        cursor.execute("""
            INSERT INTO notifications (id, user_id, message, type, created_at)
            VALUES (%s, %s, %s, 'WARNING', CURRENT_TIMESTAMP)
        """, (notif_id, user_id, msg))

    # 2. Alert users whose keys expired today & deactivate them
    cursor.execute("""
        SELECT ak.id, ak.name, ak.user_id 
        FROM api_keys ak
        WHERE ak.is_active = TRUE 
          AND DATE(ak.expires_at) <= CURRENT_DATE
    """)
    expired_today = cursor.fetchall()

    for key_id, key_name, user_id in expired_today:
        notif_id = str(uuid.uuid4())
        msg = f"Your API Key '{key_name}' has expired and is no longer valid."
        cursor.execute("""
            INSERT INTO notifications (id, user_id, message, type, created_at)
            VALUES (%s, %s, %s, 'ERROR', CURRENT_TIMESTAMP)
        """, (notif_id, user_id, msg))

        # Force it inactive so it drops out of active UI views
        cursor.execute("UPDATE api_keys SET is_active = FALSE WHERE id = %s", (key_id,))

    cursor.connection.commit()

    if expiring_soon or expired_today:
        # Ping the frontend via websocket so the bell icons update live
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')

    return {"message": f"Sent {len(expiring_soon)} warnings and deactivated {len(expired_today)} expired keys."}


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
              AND DATE(ak.expires_at) = CURRENT_DATE + INTERVAL '7 days'
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
              AND DATE(ak.expires_at) <= CURRENT_DATE
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


async def start_daily_api_key_alert_scheduler():
    """
    The background loop. Calculates the time to 8:00 AM, sleeps, and triggers the logic.
    """
    while True:
        now = datetime.now()
        target = datetime.combine(now.date(), time(8, 0, 0))

        # If 8:00 AM has already passed today, target tomorrow
        if now >= target:
            target += timedelta(days=1)

        seconds_until_target = (target - now).total_seconds()
        print(f"⏰ API Key alert check scheduled in {seconds_until_target / 3600:.2f} hours.")

        # Sleep until exactly 8:00 AM
        await asyncio.sleep(seconds_until_target)

        # Execute the check
        try:
            print("🔔 Running daily API key expiration check...")
            await run_api_key_expiration_check()
        except Exception as e:
            print(f"🚨 Error running API key alert task: {e}")

        # Sleep for 60 seconds to prevent double-firing at the exact same minute
        await asyncio.sleep(60)