import uuid
from datetime import datetime
from fastapi import HTTPException, status
from audit_logger import log_audit_event
from utils.kiss24_service import verify_kiss24_api_key
from utils.security_cipher import get_cipher


def check_system_status(cursor):
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    return {"setup_required": count == 0}


def get_system_time():
    now = datetime.now()
    iso = now.isocalendar()
    return {"year": iso[0], "week": iso[1]}


def get_all_users(cursor):
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


def create_user(cursor, u, current_user: dict):
    if u.role.value == 'read_only' or u.role.value == 'maintainer':
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None
    loc_id = str(u.location_id) if u.location_id else None
    sl_id = str(u.service_lane_id) if u.service_lane_id else None
    new_user_id = str(uuid.uuid4())

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
    return {"message": f"User {u.name} whitelisted in the database.", "id": new_user_id}


def delete_user(cursor, user_id: str, current_user: dict):
    cursor.execute("SELECT COUNT(*) FROM assignments WHERE user_id = %s", (user_id,))
    assign_count = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM events WHERE user_id = %s", (user_id,))
    event_count = cursor.fetchone()[0]

    if assign_count == 0 and event_count == 0:
        cursor.execute("DELETE FROM users WHERE id = %s", (user_id,))
        cursor.connection.commit()
        return {"message": "User permanently deleted."}
    else:
        current_year = datetime.now().year
        current_week = datetime.now().isocalendar()[1]

        cursor.execute('UPDATE users SET end_year = %s, end_week = %s WHERE id = %s',
                       (current_year, current_week, user_id))
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="USER_DELETED",
            resource_type="USER",
            resource_id=str(user_id),
            details=f"User with ID: {user_id} was deleted."
        )
        return {"message": "User successfully offboarded."}


def update_user(cursor, user_id: str, u, current_user: dict):
    if u.role == 'read_only' or u.role == 'maintainer':
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None
    loc_id = str(u.location_id) if u.location_id else None
    sl_id = str(u.service_lane_id) if u.service_lane_id else None

    cursor.execute("SELECT role FROM users WHERE id = %s", (user_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_role = str(row[0]).strip().lower()
    new_role = str(u.role.value if hasattr(u.role, 'value') else u.role).strip().lower()

    if old_role != new_role:
        cursor.execute("DELETE FROM api_keys WHERE user_id = %s", (user_id,))
        message = f"Your role was changed from '{old_role}' to '{new_role}'. For security reasons, all your active API keys have been revoked."
        cursor.execute(
            "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, 'REMOVAL', CURRENT_TIMESTAMP)",
            (str(uuid.uuid4()), user_id, message))

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
    return {"message": "User updated."}


def update_my_kiss24_key(cursor, payload, current_user: dict):
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


def validate_stored_kiss24_key(cursor, current_user: dict):
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


def get_my_profile(cursor, current_user: dict):
    cursor.execute("SELECT kiss24_api_key FROM users WHERE id = %s", (str(current_user["id"]),))
    row = cursor.fetchone()
    profile = dict(current_user)
    profile["has_kiss24_key"] = bool(row and row[0])
    return profile


def get_my_notifications(cursor, current_user: dict):
    cursor.execute("""
        SELECT id, message, type, created_at 
        FROM notifications 
        WHERE user_id = %s AND (is_read = FALSE OR is_read IS NULL)
        ORDER BY created_at DESC
    """, (str(current_user['id']),))
    return [{"id": str(r[0]), "message": r[1], "type": r[2], "created_at": r[3]} for r in cursor.fetchall()]


def mark_notifications_read(cursor, current_user: dict):
    cursor.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = %s", (str(current_user['id']),))
    cursor.connection.commit()
    return {"message": "Notifications marked as read."}


def get_user_public_keys(cursor):
    cursor.execute("SELECT id, name, public_key FROM users WHERE end_year IS NULL")
    return [{"id": str(r[0]), "name": r[1], "public_key": r[2], "has_key": r[2] is not None} for r in cursor.fetchall()]


def update_my_public_key(cursor, payload, current_user: dict):
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