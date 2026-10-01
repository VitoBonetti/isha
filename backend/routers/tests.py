from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException, Query
from database import get_db
from sqlalchemy.orm import Session
from sqlalchemy import text
from datetime import date
from typing import Optional, List
from sqlalchemy.dialects.postgresql import insert
from routers.auth import (
    get_current_user,
    require_admin,
    require_write_access,
    require_maintainer_or_admin,
    require_admin_or_read_only
)
from websockets_manager import manager
from schema import (
    TestCreate,
    TestBase,
    TestSchedule,
    BulkTestCreate,
    AssignmentCreate,
    RequirementCreate,
    MilestoneUpdate
)
from models.tests import Tests, TestAnalysis, TestAssets
from models.assets import Assets
from models.raw_assets import RawAssets
from models.services import ServiceLanes
from system_services import test_service
from utils.timeaware import aware_utcnow
from utils.memory_cache import invalidate_board_cache

router = APIRouter(prefix="/api/tests", tags=["Tests & Assignments"])


@router.post(
    "/",
    summary="[Admin/Maintainer] Create a new Test"
)
def create_test(t: TestCreate, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Manually create a new penetration test or compliance review.

    Creates a new test record linked to a specific service lane.
    It clears the cache and broadcasts a WebSocket event to all connected clients to refresh the Kanban board.
    """
    res = test_service.create_test(db, t, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.get(
    "/",
    summary="Get All Tests"
)
def get_all_tests(
    service_lane_name: Optional[str] = Query(None, description="Filter by exact Service Lane name (case-insensitive)"),
    start_date: Optional[date] = Query(None, description="Start date (YYYY-MM-DD) to filter tests"),
    end_date: Optional[date] = Query(None, description="End date (YYYY-MM-DD) to filter tests"),
    pentester_emails: Optional[List[str]] = Query(None, description="Filter by assigned pentester email(s)"),
    ritm_status: Optional[str] = Query(None, description="Filter by RITM match: 'matched' or 'unmatched'"),
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Retrieve a robustly filtered list of all tests.

    Retrieves all tests in the system. Includes advanced query parameters to filter by
    assigned pentesters, scheduled date ranges, service lanes, and ServiceNow RITM linkage status.
    """
    return test_service.get_all_tests(
        db=db,
        current_user=current_user,
        service_lane_name=service_lane_name,
        start_date=start_date,
        end_date=end_date,
        pentester_emails=pentester_emails,
        ritm_status=ritm_status
    )


@router.get(
    "/{test_id}",
    summary="Get Full Test Details & Contacts"
)
def get_test_details(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the complete profile for a single test.

    Fetches the deep details of a specific test, including its associated raw assets,
    assigned team members, linked country/asset contacts, and ServiceNow RITM tracking IDs.
    """
    return test_service.get_test_details(db, test_id, current_user)


@router.put(
    "/{test_id}",
    summary="[Admin/Maintainer] Update a specific test"
)
def update_test(test_id: str, t: TestBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Modify the core metadata of an existing test.

    Updates a test's configuration (like its name, service lane, KISS24 ID, and required credits).
    """
    res = test_service.update_test(db, test_id, t, current_user, background_tasks)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete(
    "/{test_id}",
    summary="[Admin/Maintainer] Delete a specific test"
)
def delete_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Remove a test from the database permanently.

    Deletes a test entirely. It frees up its linked assets back to the active pool
    and notifies all active UI clients to refresh.
    """
    res = test_service.delete_test(db, test_id, current_user, background_tasks)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.post(
    "/bulk",
    summary="[Admin/Maintainer] Bulk Test Creation"
)
def bulk_create_tests(req: BulkTestCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_maintainer_or_admin)):
    """
    Generate multiple tests from the active asset pool simultaneously.

    Accepts a list of asset IDs from the Active Pool and kicks off a background task
    to automatically generate unscheduled tests for all of them based on their default configurations.
    """
    sl_id = str(current_user.get('service_lane_id')) if current_user.get('service_lane_id') else None
    background_tasks.add_task(test_service.process_bulk_tests_background, req.asset_ids, str(current_user['id']),
                              str(current_user['role']), sl_id)
    background_tasks.add_task(invalidate_board_cache)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Generating {len(req.asset_ids)} tests from active pool."}


@router.post(
    "/{test_id}/workspace",
    summary="Create Test Workspace"
)
def provision_workspace_manually(test_id: str, background_tasks: BackgroundTasks,
                                 current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Provision a Google Drive workspace for the test.

    Triggers the Google Drive API to create a dedicated folder for this test,
    assign appropriate permissions, and attach the folder URL to the test record.
    """
    return test_service.provision_workspace_manually(db, test_id, current_user, background_tasks)


@router.put(
    "/{test_id}/tentative",
    summary="[Admin/Maintainer] Toggle Tentative Flag"
)
def toggle_tentative(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Mark or unmark a test schedule as 'Tentative (TBC)'.

    Toggles the visual tentative indicator for a test, letting the team know that
    the scheduled week might change.
    """
    res = test_service.toggle_tentative(db, test_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put(
    "/{test_id}/schedule",
    summary="[Admin/Maintainer] Schedule Test"
)
def schedule_test(test_id: str, schedule: TestSchedule, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Assign a test to a specific year and calendar week.

    Moves a test from the backlog into an active schedule slot (Year and ISO Week).
    This automatically triggers workspace creation if the service lane requires it.
    """
    res = test_service.schedule_test(db, test_id, schedule, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put(
    "/{test_id}/unschedule",
    summary="[Admin/Maintainer] Unschedule Test"
)
def unschedule_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Remove a test from the calendar and return it to the backlog.

    Clears the assigned year and week from a test, throwing it back into the unscheduled backlog.
    """
    res = test_service.unschedule_test(db, test_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put(
    "/{test_id}/complete",
    summary="[Admin/Maintainer] Mark Test Complete"
)
def complete_test(test_id: str, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Flag a test as fully finished and closed out.

    Moves the test to the 'COMPLETED' stage. It resolves related assets and finalizes the timeline.
    """
    res = test_service.complete_test(db, test_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.put(
    "/{test_id}/unable",
    summary="[Admin/Maintainer] Mark Test Unable"
)
def mark_test_unable(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Flag a test as permanently stopped or unable to proceed.

    Halts the test and forces it into a 'STOPPED' status. Useful for tests that get blocked
    by external dependencies or cancelled by the business.
    """
    res = test_service.mark_test_unable(db, test_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put(
    "/{test_id}/unstop",
    summary="[Admin/Maintainer] Roll back a stopped test"
)
def unstop_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Reactivate a test that was previously marked as stopped/unable.

    Revives a stopped test and returns it to an active scheduling state.
    """
    res = test_service.unstop_test(db, test_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put(
    "/{test_id}/uncomplete",
    summary="[Admin/Maintainer] Roll back a completed test"
)
def uncomplete_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_maintainer_or_admin), db: Session = Depends(get_db)):
    """
    Reopen a test that was previously marked as completed.

    Reopens a closed test and reverts its status so that further work or reporting can be done.
    """
    res = test_service.uncomplete_test(db, test_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.post(
    "/assignments",
    summary="[Admin Only] Assign Pentester"
)
def create_assignment(assign: AssignmentCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Assign a user to work on a specific test.

    Links a pentester (user) to a specific test. This determines who sees the test on their dashboard.
    """
    res = test_service.create_assignment(db, assign, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete(
    "/assignments/{test_id}/{user_id}",
    summary="[Admin Only] Remove Pentester Assignment"
)
def remove_assignment(test_id: str, user_id: str, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Unassign a user from a test.

    Removes the link between a pentester and a test, effectively taking them off the project.
    """
    res = test_service.remove_assignment(db, test_id, user_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.get(
    "/{test_id}/history",
    summary="Get Test History"
)
def get_test_history(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the audit log and timeline of events for a test.

    Returns a chronologically ordered list of all state changes, assignments, and updates
    that have occurred over the lifecycle of this specific test.
    """
    return test_service.get_test_history(db, test_id, current_user)


@router.get(
    "/{test_id}/secret",
    summary="Get Encrypted Test Secret"
)
def get_test_secret(test_id: str, current_user: dict = Depends(require_write_access), db: Session = Depends(get_db)):
    """
    Fetch the sensitive vault note for this test.

    Retrieves the AES-encrypted secret note (containing credentials, tokens, etc.) for a test.
    """
    return test_service.get_test_secret(db, test_id, current_user)


@router.put(
    "/{test_id}/secret",
    summary="Update Test Secret"
)
def update_test_secret(test_id: str, payload: dict, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_write_access), db: Session = Depends(get_db)):
    """
    Save or update the encrypted vault note.

    Writes a new AES-encrypted secret note payload to the database for this test.
    """
    res = test_service.update_test_secret(db, test_id, payload, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete(
    "/{test_id}/secret",
    summary="[Admin Only] Delete Test Secret"
)
def delete_test_secret(test_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                       db: Session = Depends(get_db)):
    """
    Permanently wipe the secure note for a test.

    Completely removes the encrypted vault entry from the database.
    """
    res = test_service.delete_test_secret(db, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.post(
    "/{test_id}/presentation",
    summary="Generate Kickoff Presentation"
)
def trigger_presentation_generation(test_id: str, background_tasks: BackgroundTasks,
                                    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Trigger the automated Google Slides generator.

    Gathers test metadata and background context, then spins up an asynchronous background task
    to generate a customized Google Slides presentation for the test.
    """
    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=403, detail="Read-only users cannot trigger generation.")

    query = db.query(
        Tests.name.label("test_name"), Tests.kiss24.label("kiss24_id"), Tests.drive_folder_id,
        ServiceLanes.name.label("service_name"), RawAssets.snow_number,
        Tests.start_week, Tests.start_year, Tests.duration_weeks
    ).outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id) \
        .outerjoin(TestAssets, Tests.id == TestAssets.test_id) \
        .outerjoin(Assets, TestAssets.asset_id == Assets.id) \
        .outerjoin(RawAssets, Assets.raw_asset_id == RawAssets.id) \
        .filter(Tests.id == test_id)

    if current_user.get('role') == 'maintainer':
        query = query.filter(
            Tests.service_lane_id == str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Test not found.")
    if not row.kiss24_id:
        raise HTTPException(status_code=400, detail="Missing kiss24 UUID.")

    background_tasks.add_task(
        test_service.process_presentation_background, test_id, str(row.kiss24_id),
        str(current_user["id"]), current_user["email"], str(current_user["role"]), row.test_name,
        row.drive_folder_id, row.service_name, row.snow_number, row.start_week, row.start_year, row.duration_weeks
    )
    return {"message": "Presentation generation started in the background."}


@router.post(
    "/{test_id}/report",
    summary="Generate PDF Final Report"
)
def trigger_report_generation(test_id: str, background_tasks: BackgroundTasks,
                              current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Trigger the automated final report builder.

    Collects test findings, formatting metadata, and context to generate a finalized
    PDF penetration testing report via a background task.
    """
    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=403, detail="Read-only users cannot trigger generation.")

    query = db.query(
        Tests.name.label("test_name"), Tests.kiss24.label("kiss24_id"), Tests.drive_folder_id,
        ServiceLanes.display_order, Tests.start_week, Tests.start_year, Tests.duration_weeks,
        ServiceLanes.name.label("service_name")
    ).outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id) \
        .filter(Tests.id == test_id)

    if current_user.get('role') == 'maintainer':
        query = query.filter(
            Tests.service_lane_id == str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Test not found.")
    if not row.kiss24_id:
        raise HTTPException(status_code=400, detail="Missing kiss24 UUID.")

    background_tasks.add_task(
        test_service.process_report_background, test_id, str(row.kiss24_id), str(current_user["id"]),
        current_user["email"], str(current_user["role"]), row.test_name, row.drive_folder_id,
        row.display_order if row.display_order is not None else 99, row.start_week, row.start_year,
        row.duration_weeks, row.service_name
    )
    return {"message": "Report generation started in the background."}


@router.post(
    "/{test_id}/vulnerabilities/report",
    summary="Generate Specific Vulnerability PDFs"
)
def trigger_vuln_reports(test_id: str, payload: dict, background_tasks: BackgroundTasks,
                         current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Generate customized PDF reports for isolated vulnerabilities.

    Takes an array of specific vulnerability UUIDs and triggers the background engine
    to compile targeted PDF reports containing only those specific findings.
    """
    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=403, detail="Read-only users cannot trigger generation.")

    vuln_uuids = payload.get("vuln_uuids", [])
    if not vuln_uuids:
        raise HTTPException(status_code=400, detail="No vulnerabilities selected.")

    query = db.query(
        Tests.name.label("test_name"), Tests.kiss24.label("kiss24_id"), Tests.drive_folder_id,
        ServiceLanes.display_order, ServiceLanes.name.label("service_name"), Tests.start_year
    ).outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id) \
        .filter(Tests.id == test_id)

    if current_user.get('role') == 'maintainer':
        query = query.filter(
            Tests.service_lane_id == str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    row = query.first()
    if not row:
        raise HTTPException(status_code=404, detail="Test not found.")
    if not row.kiss24_id:
        raise HTTPException(status_code=400, detail="Missing kiss24 UUID.")

    background_tasks.add_task(
        test_service.process_vuln_report_background, test_id, str(row.kiss24_id),
        str(current_user["id"]), current_user["email"], str(current_user["role"]), row.test_name,
        row.drive_folder_id, row.display_order if row.display_order is not None else 99, vuln_uuids,
        row.start_year, row.service_name
    )
    return {"message": f"Generating {len(vuln_uuids)} report(s) in the background!"}


@router.get(
    "/{test_id}/analysis",
    summary="Get Vulnerability AI Analysis"
)
def get_test_analysis(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the AI-generated vulnerability summary for a test.

    Fetches the generated technical analysis summarizing the security posture and findings
    associated with this specific test.
    """
    if current_user.get('role') not in ['admin', 'pentester', 'maintainer']:
        raise HTTPException(status_code=403, detail="Access denied.")

    analysis = db.query(TestAnalysis).filter(TestAnalysis.test_id == test_id).first()

    if not analysis:
        return {"status": "NONE", "analysis_text": None, "timestamp": None}

    return {
        "status": analysis.status,
        "analysis_text": analysis.analysis_text,
        "timestamp": analysis.timestamp
    }


@router.post(
    "/{test_id}/analysis",
    summary="Trigger Vulnerability Analysis"
)
def trigger_test_analysis(test_id: str, background_tasks: BackgroundTasks,
                          current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Kick off the background AI analysis engine.

    Triggers an asynchronous task to analyze the test's findings via Keep Secure 24
    and store the resulting intelligence locally.
    """
    if current_user.get('role') not in ['admin', 'pentester']:
        raise HTTPException(status_code=403, detail="Access denied.")

    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test or not test.kiss24:
        raise HTTPException(status_code=400, detail="Missing Kiss24 UUID.")

    # SQLAlchemy Upsert
    stmt = insert(TestAnalysis).values(
        test_id=test_id, status='PENDING', timestamp=aware_utcnow()
    ).on_conflict_do_update(
        index_elements=['test_id'],
        set_={'status': 'PENDING', 'analysis_text': None, 'timestamp': aware_utcnow()}
    )
    db.execute(stmt)
    db.commit()

    background_tasks.add_task(test_service.process_vuln_analysis_background, test_id, str(test.kiss24),
                              str(current_user["id"]), current_user["email"], test.name)
    return {"message": "Analysis started in the background."}


@router.get(
    "/{test_id}/milestones",
    summary="Get Test Milestones"
)
def get_milestones(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the workflow progress checklists for the test.

    Returns a dictionary of standard milestones (e.g., Intake Meeting, Report Sent) and their completion status.
    """
    return test_service.get_milestones(db, test_id, current_user)


@router.put(
    "/{test_id}/milestones",
    summary="Update Test Milestone"
)
def update_milestone(test_id: str, payload: MilestoneUpdate, current_user: dict = Depends(require_write_access),
                     db: Session = Depends(get_db)):
    """
    Toggle the completion state of a specific milestone.

    Updates the boolean state (true/false) of a specific milestone step in the test's workflow.
    """
    return test_service.update_milestone(db, test_id, payload, current_user)


@router.get(
    "/{test_id}/requirements",
    summary="Get Test Requirements"
)
def get_requirements(test_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Fetch custom requirements and scoping rules.

    Retrieves the list of specific technical or operational requirements assigned to the test.
    """
    return test_service.get_requirements(db, test_id, current_user)


@router.post(
    "/{test_id}/requirements",
    summary="Add Test Requirement"
)
def add_requirement(test_id: str, req: RequirementCreate, current_user: dict = Depends(require_write_access),
                    db: Session = Depends(get_db)):
    """
    Append a new requirement to the test's scope.

    Creates a new technical or operational requirement record for the test.
    """
    return test_service.add_requirement(db, test_id, req, current_user)


@router.delete(
    "/requirements/{req_id}",
    summary="Delete Test Requirement"
)
def delete_requirement(req_id: str, current_user: dict = Depends(require_write_access), db: Session = Depends(get_db)):
    """
    Remove a requirement from the scope.

    Deletes a specific requirement from the test's record permanently.
    """
    return test_service.delete_requirement(db, req_id, current_user)


@router.put(
    "/requirements/{req_id}/toggle",
    summary="Toggle Requirement Status"
)
def toggle_requirement(req_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Mark a requirement as fulfilled or unfulfilled.

    Flips the boolean completed status of a specific scoping requirement.
    """
    return test_service.toggle_requirement(db, req_id, current_user)