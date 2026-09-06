import uuid
from datetime import datetime
from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
from schema import UserCreate, UserBase, Kiss24KeyUpdate, PublicKeyUpdate
from websockets_manager import manager
from audit_logger import log_audit_event
from utils.secret_manager import get_secret
from utils.kiss24_service import verify_kiss24_api_key
from utils.security_cipher import get_cipher

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/system/status")
def check_system_status(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Simply checks if the board has been initialized at least once
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    return {"setup_required": count == 0}


@router.get("/system/time", summary="Get Server Time")
def get_system_time(current_user: dict = Depends(get_current_user)):
    now = datetime.now()
    iso = now.isocalendar()
    return {"year": iso[0], "week": iso[1]}


@router.get("/", summary="[Admin Only]")
def get_all_users(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to get all users
    """
    # Added service_lane_id to the SELECT
    cursor.execute("""
        SELECT id, email, name, role, base_capacity, start_week, start_year, end_week, end_year, location_id, kiss24_uuid, kiss24_api_key, service_lane_id   
        FROM users ORDER BY name
    """)
    users = []
    for r in cursor.fetchall():
        users.append({
            "id": r[0], "email": r[1], "name": r[2], "role": r[3],
            "base_capacity": r[4], "start_week": r[5], "start_year": r[6],
            "end_week": r[7], "end_year": r[8], "location_id": r[9], "kiss24_uuid": r[10],
            "kiss24_api_key": r[11], "service_lane_id": r[12]
        })
    return users


@router.post("/", summary="[Admin Only]")
def create_user(u: UserCreate, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to create new user
    """
    # Base capacity overrides
    if u.role.value == 'read_only' or u.role.value == 'maintainer':
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None

    # Safely convert UUIDs to string
    loc_id = str(u.location_id) if u.location_id else None
    sl_id = str(u.service_lane_id) if u.service_lane_id else None
    new_user_id = str(uuid.uuid4())

    # Added service_lane_id to INSERT
    cursor.execute(
        '''INSERT INTO users (id, email, name, role, location_id, base_capacity, start_week, start_year, end_week, end_year, service_lane_id)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
        (new_user_id, u.email.lower(), u.name, u.role.value, loc_id, u.base_capacity, u.start_week, u.start_year, ew,
         ey, sl_id)
    )

    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="USER_CREATED",
        resource_type="USER",
        resource_id=str(new_user_id),
        details=f"User with ID: {new_user_id} was created."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"User {u.name} whitelisted in the database."}


@router.delete("/{user_id}", summary="[Admin Only]")
def delete_user(user_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    SMART DELETE:

    - If the user has no historical assignments or events (e.g., a fake/test user), we hard-delete them.
    - If they have history, we soft-delete them by setting their end_year and end_week to today to preserve board data.
    """
    cursor.execute("SELECT COUNT(*) FROM assignments WHERE user_id = %s", (user_id,))
    assign_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM events WHERE user_id = %s", (user_id,))
    event_count = cursor.fetchone()[0]

    if assign_count == 0 and event_count == 0:
        # HARD DELETE: Wipe the test/fake user completely
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        cursor.connection.commit()
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        return {"message": "User permanently deleted."}
    else:
        # SOFT DELETE: Preserve historical data for real users
        current_year = datetime.now().year
        current_week = datetime.now().isocalendar()[1]

        cursor.execute(
            'UPDATE users SET end_year = %s, end_week = %s WHERE id = %s',
            (current_year, current_week, user_id)
        )

        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="USER_DELETED",
            resource_type="USER",
            resource_id=str(user_id),
            details=f"User with ID: {user_id} was deleted."
        )

        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        return {"message": "User successfully offboarded."}


@router.put("/{user_id}", summary="[Admin Only]")
def update_user(user_id: str, u: UserBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to update a user.

    On role change any Isha API keys are revoked.
    """
    # Base capacity overrides
    if u.role == 'read_only' or u.role == 'maintainer':
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None
    loc_id = str(u.location_id) if u.location_id else None
    sl_id = str(u.service_lane_id) if u.service_lane_id else None

    # revoking the keys
    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_role = str(row[0]).strip().lower()
    new_role = str(u.role.value if hasattr(u.role, 'value') else u.role).strip().lower()

    if old_role != new_role:
        cursor.execute("DELETE FROM api_keys WHERE user_id = %s", (user_id,))

        message = f"Your role was changed from '{old_role}' to '{new_role}'. For security reasons, all your active API keys have been revoked."
        new_notif_id = str(uuid.uuid4())
        cursor.execute("""
            INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, 'REMOVAL', CURRENT_TIMESTAMP)
        """, (new_notif_id, user_id, message))

    # Added service_lane_id to UPDATE
    cursor.execute(
        '''UPDATE users 
           SET name=%s, role=%s, location_id=%s, base_capacity=%s, 
               start_week=%s, start_year=%s, end_week=%s, end_year=%s, service_lane_id=%s
           WHERE id=%s''',
        (u.name, u.role.value if hasattr(u.role, 'value') else u.role, loc_id, u.base_capacity, u.start_week,
         u.start_year, ew, ey, sl_id, user_id)
    )
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="USER_UPDATED",
        resource_type="USER",
        resource_id=str(user_id),
        details=f"User with ID: {user_id} was updated."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "User updated."}


@router.post("/me/kiss24-key", summary="Securely store personal KISS24 API Key")
def update_my_kiss24_key(payload: Kiss24KeyUpdate, current_user: dict = Depends(get_current_user),
                         cursor=Depends(get_db_cursor)):
    """
    Securely store personal Kiss24 API Key.
    """
    clean_key = payload.api_key.strip()

    is_valid, msg = verify_kiss24_api_key(clean_key)
    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Keep Secure 24 rejected this API Key: {msg}")

    cipher = get_cipher()
    encrypted_key = cipher.encrypt(clean_key.encode('utf-8')).decode('utf-8')

    cursor.execute("UPDATE users SET kiss24_api_key = %s WHERE id = %s", (encrypted_key, str(current_user["id"])))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user.get("role", "pentester"),
        action="KISS24_API_KEY_UPDATED",
        resource_type="USER",
        resource_id=str(current_user["id"]),
        details="User securely updated their Keep Secure 24 API key."
    )
    return {"message": "Keep Secure 24 API key validated and securely stored."}


@router.get("/me/kiss24-key/validate", summary="Check if stored key is still valid")
def validate_stored_kiss24_key(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Validate stored Kiss24 key is still valid.
    """
    cursor.execute("SELECT kiss24_api_key FROM users WHERE id = %s", (str(current_user["id"]),))
    row = cursor.fetchone()

    if not row or not row[0]:
        return {"is_valid": False, "message": "No API key configured."}

    cipher = get_cipher()
    try:
        decrypted_key = cipher.decrypt(row[0].encode('utf-8')).decode('utf-8')
    except Exception:
        return {"is_valid": False, "message": "Failed to decrypt API key."}

    is_valid, msg = verify_kiss24_api_key(decrypted_key)
    return {"is_valid": is_valid, "message": msg}


@router.get("/me")
def get_my_profile(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # Check if user has a kiss24 key
    cursor.execute("SELECT kiss24_api_key FROM users WHERE id = %s", (str(current_user["id"]),))
    row = cursor.fetchone()

    # Create a mutable dictionary and add the boolean flag
    profile = dict(current_user)
    profile["has_kiss24_key"] = bool(row and row[0])
    return profile


# --- NOTIFICATIONS RESTORED ---
@router.get("/me/notifications")
def get_my_notifications(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Get all notifications for current user.
    """
    cursor.execute("""
        SELECT id, message, type, created_at 
        FROM notifications 
        WHERE user_id = %s AND (is_read = FALSE OR is_read IS NULL)
        ORDER BY created_at DESC
    """, (str(current_user['id']),))

    notifs = [{"id": str(r[0]), "message": r[1], "type": r[2], "created_at": r[3]} for r in cursor.fetchall()]
    return notifs


@router.put("/me/notifications/read")
def mark_notifications_read(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Mark notifications for current user.
    """
    cursor.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = %s", (str(current_user['id']),))
    cursor.connection.commit()
    return {"message": "Notifications marked as read."}


# public key
@router.get("/public-keys", summary="Get all users with configured public keys")
def get_user_public_keys(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Only fetch active users who have actually set up a public key
    """
    cursor.execute("SELECT id, name, public_key FROM users WHERE end_year IS NULL")

    return [
        {
            "id": str(r[0]),
            "name": r[1],
            "public_key": r[2],
            "has_key": r[2] is not None
        } for r in cursor.fetchall()
    ]


@router.post("/me/public-key", summary="Securely store personal E2EE Public Key")
def update_my_public_key(payload: PublicKeyUpdate, current_user: dict = Depends(get_current_user),
                         cursor=Depends(get_db_cursor)):
    if "PRIVATE KEY" in payload.public_key.upper():
        raise HTTPException(status_code=400,
                            detail="WARNING: You pasted a PRIVATE key! Never share this. Please upload the PUBLIC key.")

    cursor.execute("UPDATE users SET public_key = %s WHERE id = %s",
                   (payload.public_key.strip(), str(current_user["id"])))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user.get("role", "pentester"),
        action="E2EE_PUBLIC_KEY_UPDATED",
        resource_type="USER",
        resource_id=str(current_user["id"]),
        details="User generated and vaulted a new E2EE Public Key."
    )
    return {"message": "Public Key successfully linked to your account."}