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

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"


# --- 1. THE GITHUB OAUTH HANDSHAKE ---

@router.get("/github/callback", include_in_schema=False)
async def github_callback(code: str, cursor=Depends(get_db_cursor)):
    # 1. Start the Async Client session
    async with httpx.AsyncClient() as client:
        # Exchange code for token
        token_resp = await client.post(
            "https://github.com/login/oauth/access_token",
            data={
                "client_id": GITHUB_CLIENT_ID,
                "client_secret": GITHUB_CLIENT_SECRET,
                "code": code
            },
            headers={"Accept": "application/json"}
        )
        token_data = token_resp.json()
        access_token = token_data.get("access_token")

        if not access_token:
            raise HTTPException(status_code=400, detail="Failed to authenticate with GitHub")

        # Get User info
        user_resp = await client.get(
            "https://api.github.com/user",
            headers={"Authorization": f"token {access_token}"}
        )
        gh_user = user_resp.json()

        # Fallback for private emails (Notice this is safely INSIDE the 'async with' block now)
        email = gh_user.get("email")
        if not email:
            email_resp = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}"}
            )
            emails = email_resp.json()
            primary = next((e for e in emails if e.get('primary')), None)
            email = primary['email'] if primary else None

    # --- CLIENT SAFELY CLOSES HERE ---

    if not email:
        return Response(status_code=302, headers={"Location": "http://localhost:5173/login?error=no_email"})

    avatar_url = gh_user.get("avatar_url")
    github_id = str(gh_user.get("id"))
    name = gh_user.get("name") or gh_user.get("login")

    # --- 2-STEP VERIFICATION LOGIC ---
    cursor.execute("SELECT id, role FROM users WHERE email = %s", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        # User Exists: Update their GitHub-specific fields
        cursor.execute(
            "UPDATE users SET github_id = %s, avatar_url = %s, name = %s WHERE email = %s",
            (github_id, avatar_url, name, email)
        )
        cursor.connection.commit()
    else:
        # User NOT Found: Redirect to login with "Not Invited" error
        return Response(status_code=302, headers={"Location": "http://localhost:5173/login?error=not_invited"})

    # Issue JWT
    token = jwt.encode({"sub": email}, SECRET_KEY, algorithm=ALGORITHM)

    # Redirect to dashboard and set cookie
    response = Response(status_code=302, headers={"Location": "http://localhost:5173/dashboard"})
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400
    )
    return response


# --- 2. SECURITY MIDDLEWARE (DUAL-AUTH) ---

api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def hash_api_key(api_key: str) -> str:
    """Hashes the API key using SHA-256 for secure storage."""
    return hashlib.sha256(api_key.encode()).hexdigest()


def get_current_user(request: Request, api_key: str = Depends(api_key_header), cursor=Depends(get_db_cursor)):
    # METHOD A: API KEY AUTHENTICATION (For Scripts & Integrations)
    if api_key:
        hashed = hash_api_key(api_key)
        cursor.execute("""
            SELECT u.id, u.email, u.name, u.role, u.location_id, u.avatar_url 
            FROM users u
            JOIN api_keys ak ON u.id = ak.user_id
            WHERE ak.hashed_key = %s AND ak.is_active = TRUE
        """, (hashed,))
        user = cursor.fetchone()

        if not user:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked API Key")

        return {
            "id": user[0], "email": user[1], "name": user[2], "role": user[3], "location_id": user[4],
            "avatar_url": user[5]
        }

    # METHOD B: JWT COOKIE AUTHENTICATION (For the React Frontend)
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Provide a valid Cookie or X-API-Key header."
        )

    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        email: str = payload.get("sub")
        if email is None:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    cursor.execute("SELECT id, email, name, role, location_id, avatar_url FROM users WHERE email = %s", (email,))
    user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User no longer exists.")

    return {
        "id": user[0],
        "email": user[1],
        "name": user[2],
        "role": user[3],
        "location_id": user[4],
        "avatar_url": user[5]
    }


def require_admin(current_user: dict = Depends(get_current_user)):
    if current_user.get('role') != 'admin':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin privileges required.")
    return current_user


def require_write_access(current_user: dict = Depends(get_current_user)):
    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail="Read-only account cannot perform this action.")
    return current_user


# --- 3. SESSION & API KEY MANAGEMENT ---
@router.get("/keys")
def list_api_keys(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """Lists API keys. Admins see all keys, regular users see only their own."""

    if current_user['role'] == 'admin':
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
    """Generates a new API Key. The raw key is ONLY returned once."""
    # Generate a cryptographically secure string (e.g. isha_abc123xyz...)
    raw_key = "isha_" + secrets.token_urlsafe(32)
    prefix = raw_key[:10]  # e.g. "isha_ab"
    hashed = hash_api_key(raw_key)
    new_id = str(uuid.uuid4())

    cursor.execute(
        """INSERT INTO api_keys (id, user_id, name, prefix, hashed_key, created_at, is_active) 
           VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP, TRUE)""",
        (new_id, str(current_user['id']), req.name, prefix, hashed)
    )
    cursor.connection.commit()

    return {
        "id": new_id,
        "name": req.name,
        "prefix": prefix,
        "raw_key": raw_key,
        "message": "Store this key safely! It will not be shown again."
    }


@router.delete("/keys/{key_id}")
def revoke_api_key(key_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """Deletes an API key. Admins can delete any key, users can only delete their own."""
    if current_user['role'] == 'admin':
        cursor.execute("DELETE FROM api_keys WHERE id = %s", (key_id,))
    else:
        cursor.execute("DELETE FROM api_keys WHERE id = %s AND user_id = %s", (key_id, str(current_user['id'])))
    cursor.connection.commit()
    return {"message": "API Key successfully revoked."}


@router.post("/logout")
def logout(response: Response, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    response.delete_cookie(key="access_token", httponly=True, secure=False, samesite="lax")
    background_tasks.add_task(
        manager.broadcast,
        f'{{"action": "USER_LEFT", "email": "{current_user["email"]}"}}'
    )
    return {"message": "Successfully logged out"}