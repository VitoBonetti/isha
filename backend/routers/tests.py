from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
from typing import List
import uuid
from pydantic import BaseModel, UUID4
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin
from websockets_manager import manager
from schema import TestCreate, TestBase, AssignmentBase

router = APIRouter(prefix="/api/tests", tags=["Tests & Assignments"])


# --- SCHEMAS FOR SCHEDULING ---
class TestSchedule(BaseModel):
    start_week: int
    start_year: int


class BulkTestCreate(BaseModel):
    asset_ids: List[UUID4]


class AssignmentCreate(BaseModel):
    test_id: UUID4
    user_id: UUID4
    week_number: int
    year: int
    allocated_credits: float


# --- 1. CORE TEST MANAGEMENT ---

@router.post("/")
def create_test(t: TestCreate, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    new_test_id = str(uuid.uuid4())
    cursor.execute('''
        INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, status) 
        VALUES (%s, %s, %s, %s, %s, 'Not Planned') RETURNING id
    ''', (new_test_id, t.name, t.service_lane_id, t.credits_per_week, t.duration_weeks))

    new_id = cursor.fetchone()[0]

    # Link selected assets and mark them as assigned in the active pool
    if t.asset_ids:
        for asset_id in t.asset_ids:
            cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_id, asset_id))
            cursor.execute('UPDATE assets SET is_assigned = TRUE WHERE id = %s', (asset_id,))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')

    return {"message": "Test created successfully", "id": new_id}


@router.put("/{test_id}")
def update_test(test_id: str, t: TestBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # If a test is moved back to Not Planned, wipe its schedule and assignments
    if t.status == 'Not Planned':
        cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
        cursor.execute('UPDATE tests SET start_week = NULL, start_year = NULL WHERE id = %s', (test_id,))

    cursor.execute('''
        UPDATE tests 
        SET name=%s, service_lane_id=%s, credits_per_week=%s, duration_weeks=%s, status=%s
        WHERE id=%s
    ''', (t.name, t.service_lane_id, t.credits_per_week, t.duration_weeks, t.status, test_id))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')

    return {"message": "Test updated successfully."}


@router.delete("/{test_id}")
def delete_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Free up the assets back to the active pool
    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))
    for (asset_id,) in cursor.fetchall():
        cursor.execute('UPDATE assets SET is_assigned = FALSE WHERE id = %s', (asset_id,))

    # Cascade deletes
    cursor.execute('DELETE FROM test_assets WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM tests WHERE id = %s', (test_id,))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')

    return {"message": "Test permanently deleted and assets freed."}


# --- 2. BULK GENERATION ---

def process_bulk_tests_background(asset_ids: List[UUID4]):
    with db_cursor_context() as cursor:
        if not cursor: return

        for asset_id in asset_ids:
            # Look up the asset's pre-assigned service lane (Forecast)
            cursor.execute('''
                SELECT a.name, a.service_forecast_id, s.default_credits, s.default_duration_weeks 
                FROM assets a
                LEFT JOIN service_lanes s ON a.service_forecast_id = s.id
                WHERE a.id = %s AND a.is_assigned = FALSE
            ''', (str(asset_id),))

            asset_data = cursor.fetchone()
            if not asset_data or not asset_data[1]:
                continue  # Skip if already assigned or lacks a forecast lane

            asset_name, service_lane_id, def_credits, def_duration = asset_data
            new_test_id = str(uuid.uuid4())

            # Create the test using the lane's defaults
            cursor.execute('''
                INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, status) 
                VALUES (%s, %s, %s, %s, %s, 'Not Planned')
            ''', (new_test_id, asset_name, service_lane_id, def_credits, def_duration))

            # Link it
            cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_test_id, str(asset_id)))
            cursor.execute('UPDATE assets SET is_assigned = TRUE WHERE id = %s', (str(asset_id),))


@router.post("/bulk")
def bulk_create_tests(req: BulkTestCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin)):
    background_tasks.add_task(process_bulk_tests_background, req.asset_ids)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Generating {len(req.asset_ids)} tests from active pool."}


# --- 3. SCHEDULING & STATUS LIFECYCLE ---

@router.put("/{test_id}/schedule")
def schedule_test(test_id: str, schedule: TestSchedule, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('UPDATE tests SET start_week = %s, start_year = %s, status = %s WHERE id = %s',
                   (schedule.start_week, schedule.start_year, "Planned", test_id))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test scheduled on the board."}


@router.put("/{test_id}/unschedule")
def unschedule_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Notify users they were dropped
    cursor.execute('SELECT user_id FROM assignments WHERE test_id = %s', (test_id,))
    assigned_users = cursor.fetchall()

    cursor.execute("SELECT name FROM tests WHERE id = %s", (test_id,))
    test_row = cursor.fetchone()

    if test_row:
        for (user_id,) in assigned_users:
            cursor.execute("INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)",
                           (user_id, f"You were removed from {test_row[0]} because it was unscheduled.", "REMOVAL"))

    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('UPDATE tests SET start_week = NULL, start_year = NULL, status = %s WHERE id = %s',
                   ("Not Planned", test_id,))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test returned to backlog."}


@router.put("/{test_id}/complete")
def complete_test(test_id: str, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE tests SET status = 'Completed' WHERE id = %s", (test_id,))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test marked as Completed."}


@router.put("/{test_id}/unable")
def mark_test_unable(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Creates a tombstone record on the board for tracking, but returns the
    original test back to the 'Not Planned' backlog.
    """
    cursor.execute('''
        SELECT name, service_lane_id, credits_per_week, duration_weeks, start_week, start_year 
        FROM tests WHERE id = %s
    ''', (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    name, service_lane_id, credits, duration, start_week, start_year = row

    # 1. Create Tombstone
    cursor.execute('''
        INSERT INTO tests (name, service_lane_id, credits_per_week, duration_weeks, start_week, start_year, status) 
        VALUES (%s, %s, %s, %s, %s, %s, 'Unable') RETURNING id
    ''', (name, service_lane_id, credits, duration, start_week, start_year))
    tombstone_id = cursor.fetchone()[0]

    # 2. Shift assignments and assets to the tombstone so history is preserved
    cursor.execute('UPDATE assignments SET test_id = %s WHERE test_id = %s', (tombstone_id, test_id))

    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))
    for (asset_id,) in cursor.fetchall():
        cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (tombstone_id, asset_id))

    # 3. Reset the original test
    cursor.execute("UPDATE tests SET start_week = NULL, start_year = NULL, status = 'Not Planned' WHERE id = %s",
                   (test_id,))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test marked as Unable. Original preserved in backlog."}


# --- 4. ASSIGNMENTS ---

@router.post("/assignments")
def create_assignment(assign: AssignmentCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Prevent double assignment on the exact same week
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
    ''', (new_assignment_id, str(assign.test_id), str(assign.user_id), assign.week_number, assign.year, assign.allocated_credits))

    cursor.execute("SELECT name FROM tests WHERE id = %s", (str(assign.test_id),))
    test_row = cursor.fetchone()

    if test_row:
        new_notification_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO notifications (id, user_id, message, type) VALUES (%s, %s, %s, %s)",
                       (new_notification_id, str(assign.user_id), f"You were assigned to {test_row[0]} for Week {assign.week_number}.",
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
        cursor.execute("INSERT INTO notifications (user_id, message, type) VALUES (%s, %s, %s)",
                       (user_id, f"You were removed from {test_row[0]}.", "REMOVAL"))

    cursor.execute('DELETE FROM assignments WHERE test_id = %s AND user_id = %s', (test_id, user_id))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Successfully Unassigned"}