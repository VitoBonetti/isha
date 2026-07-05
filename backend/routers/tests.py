from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List
import uuid
from pydantic import BaseModel, UUID4
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin
from websockets_manager import manager
from schema import TestCreate, TestBase, AssignmentBase, TestSchedule, BulkTestCreate, AssignmentCreate

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


# --- HELPER: TEST HISTORY LOGGER ---
def log_test_history(cursor, test_id: str, user_id: str, action: str, details: str = None):
    new_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO test_history (id, test_id, user_id, action, details, timestamp)
        VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)
    ''', (new_id, test_id, str(user_id) if user_id else None, action, details))


# --- 1. CORE TEST MANAGEMENT ---
@router.post("/")
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
            cursor.execute('UPDATE assets SET is_assigned = TRUE WHERE id = %s', (str(asset_id),))

    log_test_history(cursor, new_id, current_user['id'], "CREATED", f"Test manually created.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test created successfully", "id": new_id}


@router.put("/{test_id}")
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


@router.delete("/{test_id}")
def delete_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))
    for (asset_id,) in cursor.fetchall():
        cursor.execute('UPDATE assets SET is_assigned = FALSE WHERE id = %s', (str(asset_id),))

    cursor.execute('DELETE FROM test_assets WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM tests WHERE id = %s', (test_id,))
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test permanently deleted and assets freed."}


# --- 2. BULK GENERATION ---
def process_bulk_tests_background(asset_ids: List[UUID4], user_id: str):
    with db_cursor_context() as cursor:
        if not cursor: return
        for asset_id in asset_ids:
            cursor.execute('''
                SELECT r.name, r.service_forecast_id
                FROM assets a
                JOIN raw_assets r ON a.raw_asset_id = r.id
                WHERE a.id = %s AND (a.is_assigned = FALSE OR a.is_assigned IS NULL)
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
            cursor.execute('UPDATE assets SET is_assigned = TRUE WHERE id = %s', (str(asset_id),))
            log_test_history(cursor, new_test_id, user_id, "GENERATED", f"Test generated from Asset Pool.")

        cursor.connection.commit()


@router.post("/bulk")
def bulk_create_tests(req: BulkTestCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin)):
    background_tasks.add_task(process_bulk_tests_background, req.asset_ids, str(current_user['id']))
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Generating {len(req.asset_ids)} tests from active pool."}


# --- 3. SCHEDULING & STATUS LIFECYCLE ---
@router.put("/{test_id}/schedule")
def schedule_test(test_id: str, schedule: TestSchedule, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('UPDATE tests SET start_week = %s, start_year = %s, stages = %s WHERE id = %s',
                   (schedule.start_week, schedule.start_year, "SCHEDULED", test_id))

    log_test_history(cursor, test_id, current_user['id'], "SCHEDULED",
                     f"Scheduled for Week {schedule.start_week}, {schedule.start_year}.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test scheduled on the board."}


@router.put("/{test_id}/unschedule")
def unschedule_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('SELECT user_id FROM assignments WHERE test_id = %s', (test_id,))
    assigned_users = cursor.fetchall()
    cursor.execute("SELECT name FROM tests WHERE id = %s", (test_id,))
    test_row = cursor.fetchone()

    if test_row:
        for (user_id,) in assigned_users:
            cursor.execute("INSERT INTO notifications (id, user_id, message, type) VALUES (%s, %s, %s, %s)",
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


@router.put("/{test_id}/complete")
def complete_test(test_id: str, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE tests SET stages = 'COMPLETED' WHERE id = %s", (test_id,))

    log_test_history(cursor, test_id, current_user['id'], "COMPLETED", "Test marked as completed.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test marked as Completed."}


@router.put("/{test_id}/unable")
def mark_test_unable(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute(
        'SELECT name, service_lane_id, credits_per_week, duration_weeks, start_week, start_year FROM tests WHERE id = %s',
        (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    name, service_lane_id, credits, duration, start_week, start_year = row

    new_tombstone_id = str(uuid.uuid4())

    # Create Tombstone
    cursor.execute('''
        INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, start_week, start_year, stages) 
        VALUES (%s, %s, %s, %s, %s, %s, %s, 'STOPPED') RETURNING id
    ''', (new_tombstone_id, f"[BLOCKED] {name}", str(service_lane_id), credits, duration, start_week, start_year))

    # Move assignments & clone assets
    cursor.execute('UPDATE assignments SET test_id = %s WHERE test_id = %s', (new_tombstone_id, test_id))
    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))
    for (asset_id,) in cursor.fetchall():
        cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_tombstone_id, str(asset_id)))

    # Revert original
    cursor.execute("UPDATE tests SET start_week = NULL, start_year = NULL, stages = 'NOT_PLANNED' WHERE id = %s",
                   (test_id,))

    log_test_history(cursor, test_id, current_user['id'], "STOPPED",
                     "Test halted. Tombstone dropped on calendar, original returned to backlog.")
    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test marked as Stopped."}


# --- 4. ASSIGNMENTS ---
@router.post("/assignments")
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
        cursor.execute("INSERT INTO notifications (id, user_id, message, type) VALUES (%s, %s, %s, %s)",
                       (str(uuid.uuid4()), str(assign.user_id), f"You were assigned to {test_row[0]} for Week {assign.week_number}.",
                        "ASSIGNMENT"))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Successfully Assigned"}


@router.delete("/assignments/{test_id}/{user_id}")
def remove_assignment(test_id: str, user_id: str, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT name FROM tests WHERE id = %s", (test_id,))
    test_row = cursor.fetchone()

    if test_row:
        cursor.execute("INSERT INTO notifications (id, user_id, message, type) VALUES (%s, %s, %s, %s)",
                       (str(uuid.uuid4()), str(user_id), f"You were removed from {test_row[0]}.", "REMOVAL"))

    cursor.execute('DELETE FROM assignments WHERE test_id = %s AND user_id = %s', (test_id, user_id))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Successfully Unassigned"}


# --- 5. HISTORY ROUTE ---
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