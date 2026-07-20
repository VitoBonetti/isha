import uuid
from fastapi import APIRouter, Depends, BackgroundTasks, status, HTTPException
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
from schema import UserCreate, UserBase
from websockets_manager import manager
from datetime import datetime

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/system/status", include_in_schema=False)
def check_system_status(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Simply checks if the board has been initialized at least once
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    return {"setup_required": count == 0}


@router.get("/", summary="[Admin Only]")
def get_all_users(current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("""
        SELECT id, email, name, role, base_capacity, start_week, start_year, end_week, end_year, location_id  
        FROM users ORDER BY name
    """)
    users = []
    for r in cursor.fetchall():
        users.append({
            "id": r[0], "email": r[1], "name": r[2], "role": r[3],
            "base_capacity": r[4], "start_week": r[5], "start_year": r[6],
            "end_week": r[7], "end_year": r[8], "location_id": r[9]
        })
    return users


@router.post("/", summary="[Admin Only]")
def create_user(u: UserCreate, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    if u.role.value == 'read_only':
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None

    # Safely convert UUID to string
    loc_id = str(u.location_id) if u.location_id else None
    new_user_id = str(uuid.uuid4())
    cursor.execute(
        '''INSERT INTO users (id, email, name, role, location_id, base_capacity, start_week, start_year, end_week, end_year)
           VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)''',
        (new_user_id, u.email.lower(), u.name, u.role.value, loc_id, u.base_capacity, u.start_week, u.start_year, ew, ey)
    )

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"User {u.name} whitelisted in the database."}

@router.delete("/{user_id}", summary="[Admin Only]")
def delete_user(user_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    SMART DELETE:
    If the user has no historical assignments or events (e.g., a fake/test user), we hard-delete them.
    If they have history, we soft-delete them by setting their end_year and end_week to today to preserve board data.
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
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        return {"message": "User successfully offboarded."}


@router.put("/{user_id}", summary="[Admin Only]")
def update_user(user_id: str, u: UserBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    if u.role == 'read_only':
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None
    loc_id = str(u.location_id) if u.location_id else None

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

    cursor.execute(
        '''UPDATE users 
           SET name=%s, role=%s, location_id=%s, base_capacity=%s, 
               start_week=%s, start_year=%s, end_week=%s, end_year=%s 
           WHERE id=%s''',
        (u.name, u.role.value, loc_id, u.base_capacity, u.start_week, u.start_year, ew, ey, user_id)
    )
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "User updated."}


@router.get("/me")
def get_my_profile(current_user: dict = Depends(get_current_user)):
    return current_user


# --- NOTIFICATIONS RESTORED ---
@router.get("/me/notifications")
def get_my_notifications(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # FIX: Account for is_read being NULL, and cast the UUID to string!
    cursor.execute("""
        SELECT id, message, type, created_at 
        FROM notifications 
        WHERE user_id = %s AND (is_read = FALSE OR is_read IS NULL)
        ORDER BY created_at DESC
    """, (str(current_user['id']),))

    # FIX: Cast the notification ID to string to prevent JSON serialization crashes
    notifs = [{"id": str(r[0]), "message": r[1], "type": r[2], "created_at": r[3]} for r in cursor.fetchall()]
    return notifs


@router.put("/me/notifications/read")
def mark_notifications_read(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # FIX: Cast the UUID to string
    cursor.execute("UPDATE notifications SET is_read = TRUE WHERE user_id = %s", (str(current_user['id']),))
    cursor.connection.commit()
    return {"message": "Notifications marked as read."}