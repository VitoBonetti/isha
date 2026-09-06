import os
from dotenv import load_dotenv
import httpx
import hashlib
import secrets
import uuid
from fastapi.security import APIKeyHeader
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status, BackgroundTasks
from jose import jwt, JWTError
from database import get_db_cursor
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
        cursor.execute("""
            SELECT u.id, u.email, u.name, u.role, u.location_id, u.service_lane_id
            FROM users u
            JOIN api_keys ak ON u.id = ak.user_id
            WHERE ak.hashed_key = %s AND ak.is_active = TRUE
        """, (hashed,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API Key")

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
        cursor.execute("""
            SELECT ak.id, ak.name as key_name, ak.prefix, ak.created_at, u.name as owner_name, u.email as owner_email
            FROM api_keys ak
            JOIN users u ON ak.user_id = u.id
            ORDER BY ak.created_at DESC
        """)
    else:
        cursor.execute("""
            SELECT id, name as key_name, prefix, created_at, NULL as owner_name, NULL as owner_email
            FROM api_keys 
            WHERE user_id = %s 
            ORDER BY created_at DESC
        """, (str(current_user['id']),))

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/keys")
def create_api_key(req: ApiKeyCreate, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Generates a new API Key. The raw key is ONLY returned once.
    Generate a cryptographically secure string (e.g. isha_abc123xyz...)
    """
    # Generate a cryptographically secure string (e.g. isha_abc123xyz...)
    raw_key = "isha_" + secrets.token_urlsafe(32)
    prefix = raw_key[:10]
    hashed = hash_api_key(raw_key)
    new_id = str(uuid.uuid4())

    cursor.execute(
        """INSERT INTO api_keys (id, user_id, name, prefix, hashed_key, created_at, is_active) 
           VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)""",
        (new_id, str(current_user['id']), req.name, prefix, hashed)
    )
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="CREATE_API_KEY",
        resource_type="USER",
        resource_id=str(new_id),
        details=f"{current_user['id']} has create a new API Key."
    )

    return {
        "id": new_id,
        "name": req.name,
        "prefix": prefix,
        "raw_key": raw_key,
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