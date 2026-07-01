import os
from dotenv import load_dotenv
import httpx
from fastapi import APIRouter, Depends, HTTPException, Response, Request, status, BackgroundTasks
from jose import jwt, JWTError
from database import get_db_cursor
from websockets_manager import manager

env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '.env')
load_dotenv(env_path)

router = APIRouter(prefix="/api/auth", tags=["Authentication"])

GITHUB_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID")
GITHUB_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET")
SECRET_KEY = os.environ.get("SECRET_KEY")
ALGORITHM = "HS256"


# --- 1. THE GITHUB OAUTH HANDSHAKE ---

@router.get("/github/callback")
async def github_callback(code: str, cursor=Depends(get_db_cursor)):
    # Exchange code for token
    token_resp = await httpx.post(
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
    user_resp = await httpx.get(
        "https://api.github.com/user",
        headers={"Authorization": f"token {access_token}"}
    )
    gh_user = user_resp.json()

    # Fallback for private emails
    email = gh_user.get("email")
    if not email:
        email_resp = await httpx.get(
            "https://api.github.com/user/emails",
            headers={"Authorization": f"token {access_token}"}
        )
        emails = email_resp.json()
        # Find primary email
        primary = next((e for e in emails if e.get('primary')), None)
        email = primary['email'] if primary else None

    if not email:
        return Response(status_code=302, headers={"Location": "http://localhost:5173/login?error=no_email"})

    avatar_url = gh_user.get("avatar_url")
    github_id = str(gh_user.get("id"))
    name = gh_user.get("name") or gh_user.get("login")

    # --- 2-STEP VERIFICATION LOGIC ---
    cursor.execute("SELECT id, role FROM users WHERE email = %s", (email,))
    existing_user = cursor.fetchone()

    if existing_user:
        # User Exists: Update their GitHub-specific fields and COMMIT
        cursor.execute(
            "UPDATE users SET github_id = %s, avatar_url = %s, name = %s WHERE email = %s",
            (github_id, avatar_url, name, email)
        )
        cursor.connection.commit()  # FIX: Commits the transaction to prevent database deadlocks
    else:
        # User NOT Found: Redirect to login with "Not Invited" error
        return Response(status_code=302, headers={"Location": "http://localhost:5173/login?error=not_invited"})

    # Issue JWT
    token = jwt.encode({"sub": email}, SECRET_KEY, algorithm=ALGORITHM)

    # Redirect to dashboard and set cookie
    response = Response(status_code=302, headers={"Location": "http://localhost:5173/dashboard"})

    # FIX: secure=False allows the browser to accept the cookie on localhost HTTP
    response.set_cookie(
        key="access_token",
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=86400  # 24 hours
    )
    return response


# --- 2. SECURITY MIDDLEWARE ---

def get_current_user(request: Request, cursor=Depends(get_db_cursor)):
    token = request.cookies.get("access_token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
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


# --- 3. SESSION MANAGEMENT ---

@router.post("/logout")
def logout(response: Response, background_tasks: BackgroundTasks, current_user: dict = Depends(get_current_user)):
    response.delete_cookie(key="access_token", httponly=True, secure=False, samesite="lax")
    background_tasks.add_task(
        manager.broadcast,
        f'{{"action": "USER_LEFT", "email": "{current_user["email"]}"}}'
    )
    return {"message": "Successfully logged out"}