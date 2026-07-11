from typing import List
import uuid
import os
import base64
import hashlib
from cryptography.fernet import Fernet
from pydantic import BaseModel, UUID4
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin, require_write_access
from websockets_manager import manager
from schema import TestCreate, TestBase, AssignmentBase, TestSchedule, BulkTestCreate, AssignmentCreate, SecureNotePayload
from audit_logger import log_audit_event

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
    new_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO test_history (id, test_id, user_id, action, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ''', (new_id, test_id, str(user_id) if user_id else None, action, details))


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

    log_test_history(cursor, test_id, current_user['id'], "UPDATED", f"Test settings updated.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test updated successfully."}


@router.delete("/{test_id}", summary="[Admin Only]")
def delete_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))

    cursor.execute('DELETE FROM test_assets WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM tests WHERE id = %s', (test_id,))
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test permanently deleted and assets freed."}


# --- BULK GENERATION ---
def process_bulk_tests_background(asset_ids: List[UUID4], user_id: str):
    with db_cursor_context() as cursor:
        if not cursor: return
        for asset_id in asset_ids:
            cursor.execute('''
                SELECT r.name, r.service_forecast_id
                FROM assets a
                JOIN raw_assets r ON a.raw_asset_id = r.id
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

            asset_name, service_lane_id = asset_data
            new_test_id = str(uuid.uuid4())

            cursor.execute('''
                INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, stages) 
                VALUES (%s, %s, %s, %s, %s, 'NOT_PLANNED') RETURNING id
            ''', (new_test_id, asset_name, str(service_lane_id), 2.0, 1))

            cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_test_id, str(asset_id)))
            log_test_history(cursor, new_test_id, user_id, "GENERATED", f"Test generated from Asset Pool.")

        cursor.connection.commit()


@router.post("/bulk", summary="[Admin Only]")
def bulk_create_tests(req: BulkTestCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin)):
    background_tasks.add_task(process_bulk_tests_background, req.asset_ids, str(current_user['id']))
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Generating {len(req.asset_ids)} tests from active pool."}


# --- SCHEDULING & STATUS LIFECYCLE ---
@router.put("/{test_id}/schedule", summary="[Admin Only]")
def schedule_test(test_id: str, schedule: TestSchedule, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
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

    cursor.execute("SELECT asset_id FROM test_assets WHERE test_id = %s", (test_id,))
    for (ast_id,) in cursor.fetchall():
        cursor.execute("SELECT raw_asset_id FROM assets WHERE id = %s", (ast_id,))
        raw_row = cursor.fetchone()
        if raw_row:
            cursor.execute("""
                INSERT INTO asset_history (id, raw_asset_id, user_id, action, details, timestamp)
                VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
            """, (str(uuid.uuid4()), str(raw_row[0]), current_user['id'], "TEST_COMPLETED", f"A test cycle was successfully completed for this asset."))

    log_test_history(cursor, test_id, current_user['id'], "COMPLETED", "Test marked as completed.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test marked as Completed."}


@router.put("/{test_id}/unable", summary="[Admin Only]")
def mark_test_unable(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    #  Fetch Original Test Details
    cursor.execute('SELECT name, service_lane_id, credits_per_week, duration_weeks FROM tests WHERE id = %s',
                   (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    name, service_lane_id, credits, duration = row

    # Keep the Original Test on the board, but mark it as STOPPED and add [BLOCKED]
    cursor.execute("UPDATE tests SET stages = 'STOPPED', name = %s WHERE id = %s", (f"[BLOCKED] {name}", test_id))

    # Release the pentester's credits by deleting assignments!
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))

    #  Create a fresh Clone in the Backlog (Clean Name)
    clone_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, stages) 
        VALUES (%s, %s, %s, %s, %s, 'NOT_PLANNED')
    ''', (clone_id, name, str(service_lane_id), credits, duration))

    # Attach the same assets to the Clone
    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))
    for (asset_id,) in cursor.fetchall():
        cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (clone_id, str(asset_id)))

    # --- COPY THE ENTIRE HISTORY TO THE CLONE! ---
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
    log_test_history(cursor, test_id, current_user['id'], "STOPPED",
                     f"Test stopped. Clone generated in backlog: {clone_id}")

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test marked as Stopped."}

@router.put("/{test_id}/unstop", summary="[Admin Only]")
def unstop_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Get the Original test
    cursor.execute("SELECT name FROM tests WHERE id = %s AND stages = 'STOPPED'", (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Stopped test not found.")

    # Strip the [BLOCKED] tag for good
    name = row[0]
    original_name = name.replace("[BLOCKED] ", "") if name.startswith("[BLOCKED] ") else name

    #  Find the Clone ID from history
    cursor.execute("""
        SELECT details FROM test_history 
        WHERE test_id = %s AND action = 'STOPPED' 
        ORDER BY timestamp DESC LIMIT 1
    """, (test_id,))
    hist_row = cursor.fetchone()

    if hist_row and "Clone generated in backlog: " in hist_row[0]:
        # Extract the secret UUID!
        clone_id = hist_row[0].split("Clone generated in backlog: ")[1].strip()

        # Check if clone is STILL in the backlog (NOT_PLANNED)
        cursor.execute("SELECT stages FROM tests WHERE id = %s", (clone_id,))
        clone_stage_row = cursor.fetchone()

        if clone_stage_row:
            if clone_stage_row[0] == 'NOT_PLANNED':
                # Safe to delete: It's still in the backlog
                cursor.execute("DELETE FROM test_assets WHERE test_id = %s", (clone_id,))
                cursor.execute("DELETE FROM tests WHERE id = %s", (clone_id,))
            else:
                # The clone is already scheduled on the board! Block the unstop.
                raise HTTPException(
                    status_code=400,
                    detail="Cannot Undo Stop: The remaining work for this test has already been rescheduled."
                )

    #  Revert Original test back to SCHEDULED and restore its clean name
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
    if test_row:
        cursor.execute("INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                       (str(uuid.uuid4()), str(assign.user_id), f"You were assigned to {test_row[0]} for Week {assign.week_number}.",
                        "ASSIGNMENT"))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Successfully Assigned"}


@router.delete("/assignments/{test_id}/{user_id}", summary="[Admin Only]")
def remove_assignment(test_id: str, user_id: str, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT name FROM tests WHERE id = %s", (test_id,))
    test_row = cursor.fetchone()
    if test_row:
        cursor.execute("INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                       (str(uuid.uuid4()), str(user_id), f"You were removed from {test_row[0]}.", "REMOVAL"))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s AND user_id = %s', (test_id, user_id))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Successfully Unassigned"}


# ---  HISTORY ROUTE ---
@router.get("/{test_id}/history")
def get_test_history(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute('''
        SELECT th.id, th.action, th.details, th.timestamp as created_at, u.name as user_name
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