from typing import List
import uuid
import os
import base64
import hashlib
from datetime import datetime
from cryptography.fernet import Fernet
from pydantic import BaseModel, UUID4
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin, require_write_access
from websockets_manager import manager
from schema import TestCreate, TestBase, AssignmentBase, TestSchedule, BulkTestCreate, AssignmentCreate, SecureNotePayload
from audit_logger import log_audit_event
from utils.drive_manager import DriveManager, background_archive_workspace, background_provision_workspace

router = APIRouter(prefix="/api/tests", tags=["Tests & Assignments"])

# --- HELPER: ENUM MAPPING ---
FRONTEND_TO_DB_STAGES = {
    "Not Planned": "NOT_PLANNED",
    "Scheduled": "SCHEDULED",
    "In Progress": "IN_PROGRESS",
    "Stopped": "STOPPED",
    "Deleted": "DELETED",
    "Completed": "COMPLETED",
    "Archived": "ARCHIVED"
}


# --- SECURITY: ENCRYPTION CIPHER ---
def get_cipher():
    secret = os.getenv("SECRET_KEY", "fallback_secret_for_development")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret.encode()).digest())
    return Fernet(key)


# --- HELPER: TEST HISTORY LOGGER ---
def log_test_history(cursor, test_id: str, user_id: str, action: str, details: str = None):
    """Logs an event to the test_history AND cascades it to the asset_history of all attached assets."""

    # log to Test History
    new_test_hist_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO test_history (id, test_id, user_id, action, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ''', (new_test_hist_id, test_id, str(user_id) if user_id else None, action, details))

    # inserte to Asset History
    cursor.execute('''
        SELECT a.raw_asset_id, t.name 
        FROM test_assets ta
        JOIN assets a ON ta.asset_id = a.id
        JOIN tests t ON ta.test_id = t.id
        WHERE ta.test_id = %s
    ''', (test_id,))
    assets_data = cursor.fetchall()

    for raw_asset_id, test_name in assets_data:
        new_asset_hist_id = str(uuid.uuid4())
        # prefix the detail so the asset history makes sense contextually
        asset_details = f"[Test: {test_name}] {details}" if details else f"[Test: {test_name}] Status updated to {action}."
        cursor.execute('''
            INSERT INTO asset_history (id, raw_asset_id, user_id, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
        ''', (new_asset_hist_id, str(raw_asset_id), str(user_id) if user_id else None, action, asset_details))


# --- CORE TEST MANAGEMENT ---
@router.post("/", summary="[Admin Only]")
def create_test(t: TestCreate, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    new_test_id = str(uuid.uuid4())

    cursor.execute('''
        INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, stages) 
        VALUES (%s, %s, %s, %s, %s, 'NOT_PLANNED') RETURNING id
    ''', (new_test_id, t.name, str(t.service_lane_id), t.credits_per_week, t.duration_weeks))
    new_id = cursor.fetchone()[0]

    if t.asset_ids:
        for asset_id in t.asset_ids:
            cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_id, str(asset_id)))

    log_test_history(cursor, new_id, current_user['id'], "CREATED", f"Test manually created.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test created successfully", "id": new_id}


@router.get("/")
def get_all_tests(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute('''
        SELECT t.id, t.name, t.start_week, t.start_year, t.duration_weeks, t.stages::text as status,
               s.name as service_lane_name, s.is_active as is_service_active,
               COALESCE((SELECT string_agg(DISTINCT u.name, ', ') FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = t.id), 'Unassigned') as assigned_pentesters,
               EXISTS(SELECT 1 FROM secret_notes WHERE test_id = t.id) as has_secret
        FROM tests t LEFT JOIN services_lanes s ON t.service_lane_id = s.id
        ORDER BY t.start_year DESC NULLS LAST, t.start_week DESC NULLS LAST, t.name ASC
    ''')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.put("/{test_id}", summary="[Admin Only]")
def update_test(test_id: str, t: TestBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    db_stage = FRONTEND_TO_DB_STAGES.get(t.status, "NOT_PLANNED")

    if db_stage == 'NOT_PLANNED':
        cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
        cursor.execute('UPDATE tests SET start_week = NULL, start_year = NULL WHERE id = %s', (test_id,))

    cat_id = str(t.category_id) if hasattr(t, 'category_id') and t.category_id else None

    cursor.execute('''
        UPDATE tests 
        SET name=%s, service_lane_id=%s, category_id=%s, credits_per_week=%s, duration_weeks=%s, stages=%s
        WHERE id=%s
    ''', (t.name, str(t.service_lane_id), cat_id, t.credits_per_week, t.duration_weeks, db_stage, test_id))

    log_test_history(cursor, test_id, current_user['id'], "UPDATED", f"Settings updated: {t.credits_per_week}cr, {t.duration_weeks}wks.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test updated successfully."}


@router.delete("/{test_id}", summary="[Admin Only]")
def delete_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):

    # Fetch test name and drive_folder_id before deleting
    cursor.execute("SELECT name, drive_folder_id FROM tests WHERE id = %s", (test_id,))
    test_data = cursor.fetchone()

    # Log deletion BEFORE removing links, so the assets receive the cascade
    log_test_history(cursor, test_id, current_user['id'], "DELETED", "Test permanently deleted and assets freed.")

    cursor.execute('DELETE FROM test_assets WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM tests WHERE id = %s', (test_id,))
    cursor.connection.commit()

    if test_data and test_data[1]:
        test_name, folder_id = test_data[0], test_data[1]
        background_tasks.add_task(background_archive_workspace, folder_id, test_name)

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test permanently deleted and assets freed."}


# --- BULK GENERATION ---
def process_bulk_tests_background(asset_ids: List[UUID4], user_id: str):
    with db_cursor_context() as cursor:
        if not cursor: return
        for asset_id in asset_ids:
            cursor.execute('''
                SELECT r.name, r.service_forecast_id, s.default_credits, s.default_duration_weeks,
                       s.name as service_name, c.name as country_name, s.auto_provision_workspace
                FROM assets a
                JOIN raw_assets r ON a.raw_asset_id = r.id
                LEFT JOIN services_lanes s ON r.service_forecast_id = s.id
                LEFT JOIN countries c ON r.country_id = c.id
                WHERE a.id = %s 
                 AND (r.duplicate_allowed = TRUE OR NOT EXISTS (
                    SELECT 1 FROM test_assets ta 
                     JOIN tests t ON ta.test_id = t.id 
                     WHERE ta.asset_id = a.id 
                         AND t.stages::text IN ('NOT_PLANNED', 'SCHEDULED', 'IN_PROGRESS')
                ))
            ''', (str(asset_id),))

            asset_data = cursor.fetchone()
            if not asset_data or not asset_data[1]: continue

            asset_name, service_lane_id, default_credits, default_duration_weeks, service_name, country_name, auto_provision = asset_data

            new_test_id = str(uuid.uuid4())
            credits = float(default_credits) if default_credits is not None else 2.0
            duration = int(default_duration_weeks) if default_duration_weeks is not None else 1

            cursor.execute('''
                INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, stages) 
                VALUES (%s, %s, %s, %s, %s, 'NOT_PLANNED') RETURNING id
            ''', (new_test_id, asset_name, str(service_lane_id), credits, duration))

            cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_test_id, str(asset_id)))
            log_test_history(cursor, new_test_id, user_id, "GENERATED", f"Test generated from Asset Pool.")

            current_year = datetime.now().year
            if auto_provision:
                DriveManager().provision_test_workspace(new_test_id, current_year, service_name, country_name,
                                                        asset_name)

        cursor.connection.commit()


@router.post("/bulk", summary="[Admin Only]")
def bulk_create_tests(req: BulkTestCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin)):
    background_tasks.add_task(process_bulk_tests_background, req.asset_ids, str(current_user['id']))
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Generating {len(req.asset_ids)} tests from active pool."}


# --- 3. SCHEDULING & STATUS LIFECYCLE ---
@router.put("/{test_id}/schedule", summary="[Admin Only]")
def schedule_test(test_id: str, schedule: TestSchedule, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Fetch old schedule to see if the dates are actively shifting
    cursor.execute('SELECT start_week, start_year, name FROM tests WHERE id = %s', (test_id,))
    test_row = cursor.fetchone()

    if test_row:
        old_week, old_year, test_name = test_row
        # If the test was already scheduled, and the target week or year has changed:
        if old_week is not None and old_year is not None:
            if old_week != schedule.start_week or old_year != schedule.start_year:
                # Find all assigned users
                cursor.execute('SELECT DISTINCT user_id FROM assignments WHERE test_id = %s', (test_id,))
                assigned_users = cursor.fetchall()

                # Notify them
                for (u_id,) in assigned_users:
                    cursor.execute(
                        "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                        (str(uuid.uuid4()), str(u_id),
                         f"You were removed from {test_name} because it was rescheduled to Week {schedule.start_week}, {schedule.start_year}.",
                         "REMOVAL"))

                # Drop assignments to unlock their capacity on the old week
                cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
                log_test_history(cursor, test_id, current_user['id'], "UNASSIGNED",
                                 "Pentesters removed due to schedule shift. Reassignment required.")

    #Proceed with updating the new schedule
    cursor.execute('UPDATE tests SET start_week = %s, start_year = %s, stages = %s WHERE id = %s',
                   (schedule.start_week, schedule.start_year, "SCHEDULED", test_id))

    log_test_history(cursor, test_id, current_user['id'], "SCHEDULED",
                     f"Scheduled for Week {schedule.start_week}, {schedule.start_year}.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test scheduled on the board."}


@router.put("/{test_id}/unschedule", summary="[Admin Only]")
def unschedule_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('SELECT user_id FROM assignments WHERE test_id = %s', (test_id,))
    assigned_users = cursor.fetchall()
    cursor.execute("SELECT name FROM tests WHERE id = %s", (test_id,))
    test_row = cursor.fetchone()

    if test_row:
        for (user_id,) in assigned_users:
            cursor.execute("INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                           (str(uuid.uuid4()), str(user_id), f"You were removed from {test_row[0]} because it was unscheduled.",
                            "REMOVAL"))

    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('UPDATE tests SET start_week = NULL, start_year = NULL, stages = %s WHERE id = %s',
                   ("NOT_PLANNED", test_id,))

    log_test_history(cursor, test_id, current_user['id'], "UNSCHEDULED",
                     "Test removed from calendar and returned to backlog.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test returned to backlog."}


@router.put("/{test_id}/complete", summary="[Admin Only]")
def complete_test(test_id: str, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE tests SET stages = 'COMPLETED' WHERE id = %s", (test_id,))

    log_test_history(cursor, test_id, current_user['id'], "COMPLETED", "Test successfully marked as completed.")

    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test marked as Completed."}


@router.put("/{test_id}/unable", summary="[Admin Only]")
def mark_test_unable(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    #  original test details
    cursor.execute('SELECT name, service_lane_id, credits_per_week, duration_weeks FROM tests WHERE id = %s',
                   (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    name, service_lane_id, credits, duration = row

    # keep the original test on the board  marked  as STOPPED and adding [BLOCKED] text as prefix
    cursor.execute("UPDATE tests SET stages = 'STOPPED', name = %s WHERE id = %s", (f"[BLOCKED] {name}", test_id))

    # release the pentesters credits by deleting assignments
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))

    clone_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, stages) 
        VALUES (%s, %s, %s, %s, %s, 'NOT_PLANNED')
    ''', (clone_id, name, str(service_lane_id), credits, duration))

    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))
    for (asset_id,) in cursor.fetchall():
        cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (clone_id, str(asset_id)))

    # copy the history to the clone
    cursor.execute("SELECT user_id, action, details, timestamp FROM test_history WHERE test_id = %s", (test_id,))
    old_history = cursor.fetchall()
    for h_user, h_action, h_details, h_time in old_history:
        new_h_id = str(uuid.uuid4())
        cursor.execute('''
            INSERT INTO test_history (id, test_id, user_id, action, details, timestamp)
            VALUES (%s, %s, %s, %s, %s, %s)
        ''', (new_h_id, clone_id, str(h_user) if h_user else None, h_action, h_details, h_time))

    #  Log the split event for both tests
    log_test_history(cursor, clone_id, current_user['id'], "CLONED", "Test resumed in backlog from stopped original.")
    log_test_history(cursor, test_id, current_user['id'], "STOPPED", f"Test stopped. Clone generated in backlog: {clone_id}")

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test marked as Stopped."}


@router.put("/{test_id}/unstop", summary="[Admin Only]")
def unstop_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):

    cursor.execute("SELECT name FROM tests WHERE id = %s AND stages = 'STOPPED'", (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Stopped test not found.")

    name = row[0]
    original_name = name.replace("[BLOCKED] ", "") if name.startswith("[BLOCKED] ") else name

    cursor.execute("""
        SELECT details FROM test_history 
        WHERE test_id = %s AND action = 'STOPPED' 
        ORDER BY timestamp DESC LIMIT 1
    """, (test_id,))
    hist_row = cursor.fetchone()

    if hist_row and "Clone generated in backlog: " in hist_row[0]:
        clone_id = hist_row[0].split("Clone generated in backlog: ")[1].strip()

        cursor.execute("SELECT stages FROM tests WHERE id = %s", (clone_id,))
        clone_stage_row = cursor.fetchone()

        if clone_stage_row:
            if clone_stage_row[0] == 'NOT_PLANNED':
                # Safe to delete: still in the backlog
                cursor.execute("DELETE FROM test_assets WHERE test_id = %s", (clone_id,))
                cursor.execute("DELETE FROM tests WHERE id = %s", (clone_id,))
            else:
                raise HTTPException(
                    status_code=400,
                    detail="Cannot Undo Stop: The remaining work for this test has already been rescheduled."
                )

    #  revert original test back to SCHEDULED and  clean its name
    cursor.execute("UPDATE tests SET name = %s, stages = 'SCHEDULED' WHERE id = %s", (original_name, test_id))

    log_test_history(cursor, test_id, current_user['id'], "UNSTOPPED", "Test unblocked and clone removed.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test unstopped successfully."}


# Make un-completing a test cleaner on the backend
@router.put("/{test_id}/uncomplete", summary="[Admin Only]")
def uncomplete_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE tests SET stages = 'SCHEDULED' WHERE id = %s", (test_id,))
    log_test_history(cursor, test_id, current_user['id'], "UNCOMPLETED", "Test reverted to Scheduled.")
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test uncompleted."}


# ---  ASSIGNMENTS ---
@router.post("/assignments", summary="[Admin Only]")
def create_assignment(assign: AssignmentCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('''
        SELECT a.id FROM assignments a
        WHERE a.user_id = %s AND a.week_number = %s AND a.year = %s AND a.test_id = %s
    ''', (str(assign.user_id), assign.week_number, assign.year, str(assign.test_id)))

    if cursor.fetchone():
        raise HTTPException(status_code=400, detail="Pentester is already assigned to this test for this week!")

    new_assignment_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO assignments (id, test_id, user_id, week_number, year, allocated_credits) 
        VALUES (%s, %s, %s, %s, %s, %s)
    ''', (new_assignment_id, str(assign.test_id), str(assign.user_id), assign.week_number, assign.year,
          assign.allocated_credits))

    cursor.execute("SELECT name FROM tests WHERE id = %s", (str(assign.test_id),))
    test_row = cursor.fetchone()

    cursor.execute("SELECT name FROM users WHERE id = %s", (str(assign.user_id),))
    user_row = cursor.fetchone()

    if test_row:
        cursor.execute(
            "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
            (str(uuid.uuid4()), str(assign.user_id),
             f"You were assigned to {test_row[0]} for Week {assign.week_number}.",
             "ASSIGNMENT"))

    # Logging assignment to test and asset History
    pentester_name = user_row[0] if user_row else "Unknown User"
    log_test_history(cursor, str(assign.test_id), current_user['id'], "ASSIGNED",
                     f"Assigned {pentester_name} for Wk {assign.week_number} ({assign.allocated_credits} cr).")

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Successfully Assigned"}


@router.delete("/assignments/{test_id}/{user_id}", summary="[Admin Only]")
def remove_assignment(test_id: str, user_id: str, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT name FROM tests WHERE id = %s", (test_id,))
    test_row = cursor.fetchone()

    cursor.execute("SELECT name FROM users WHERE id = %s", (user_id,))
    user_row = cursor.fetchone()

    if test_row:
        cursor.execute(
            "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
            (str(uuid.uuid4()), str(user_id), f"You were removed from {test_row[0]}.", "REMOVAL"))

    cursor.execute('DELETE FROM assignments WHERE test_id = %s AND user_id = %s', (test_id, user_id))

    # logging removal to test and asset History
    pentester_name = user_row[0] if user_row else "Unknown User"
    log_test_history(cursor, test_id, current_user['id'], "UNASSIGNED", f"Removed {pentester_name} from the team.")

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Successfully Unassigned"}


# ---  HISTORY ROUTE ---
@router.get("/{test_id}/history")
def get_test_history(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute('''
        SELECT th.id, th.action, th.details, th.timestamp, u.name as user_name
        FROM test_history th
        LEFT JOIN users u ON th.user_id = u.id
        WHERE th.test_id = %s
        ORDER BY th.timestamp DESC
    ''', (test_id,))
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


# --- SECURE NOTES CRUD ---
@router.get("/{test_id}/secret")
def get_test_secret(test_id: str, current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT encrypted_note FROM secret_notes WHERE test_id = %s", (test_id,))
    row = cursor.fetchone()
    if not row: return {"note": ""}
    try:
        cipher = get_cipher()
        decrypted_note = cipher.decrypt(row[0].encode()).decode()
        log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_VIEWED", "TEST_SECRET", details=f"Viewed secure note for test {test_id}.")
        return {"note": decrypted_note}
    except Exception:
        raise HTTPException(status_code=500, detail="Failed to decrypt the secure note.")


@router.put("/{test_id}/secret")
def update_test_secret(test_id: str, payload: SecureNotePayload, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    cipher = get_cipher()
    encrypted_note = cipher.encrypt(payload.note.encode()).decode()
    cursor.execute('''
        INSERT INTO secret_notes (test_id, encrypted_note, updated_at) 
        VALUES (%s, %s, CURRENT_TIMESTAMP)
        ON CONFLICT (test_id) DO UPDATE SET encrypted_note = EXCLUDED.encrypted_note, updated_at = CURRENT_TIMESTAMP
    ''', (test_id, encrypted_note))
    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_UPDATED", "TEST_SECRET", details=f"Updated secure note for test {test_id}.")
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Secure note encrypted and saved."}


@router.delete("/{test_id}/secret", summary="[Admin Only]")
def delete_test_secret(test_id: str, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM secret_notes WHERE test_id = %s", (test_id,))
    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_DELETED", "TEST_SECRET", details=f"Deleted secure note for test {test_id}.")
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Secure note permanently deleted."}


@router.post("/{test_id}/workspace", summary="[Admin Only]")
def provision_workspace_manually(test_id: str, background_tasks: BackgroundTasks,
                                 current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Fetch required metadata to create the folder path
    cursor.execute('''
        SELECT t.name, s.name, c.name, t.start_year
        FROM tests t
        LEFT JOIN services_lanes s ON t.service_lane_id = s.id
        LEFT JOIN test_assets ta ON t.id = ta.test_id
        LEFT JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN countries c ON a.country_id = c.id
        WHERE t.id = %s LIMIT 1
    ''', (test_id,))

    test_data = cursor.fetchone()
    if not test_data:
        raise HTTPException(status_code=404, detail="Test not found.")

    test_name, service_name, country_name, start_year = test_data
    target_year = start_year if start_year else datetime.now().year

    # Run the provisioner in the background. It will automatically broadcast a REFRESH_BOARD event when done!
    background_tasks.add_task(background_provision_workspace, test_id, target_year, service_name, country_name,
                              test_name)

    return {"message": "Workspace provisioning started."}