from fastapi import APIRouter, Depends, BackgroundTasks, HTTPException
from database import get_db_cursor
from routers.auth import get_current_user, require_admin, require_write_access, require_maintainer_or_admin, require_admin_or_read_only
from websockets_manager import manager
from schema import TestCreate, TestBase, TestSchedule, BulkTestCreate, AssignmentCreate, RequirementCreate, MilestoneUpdate
from system_services import test_service

router = APIRouter(prefix="/api/tests", tags=["Tests & Assignments"])


@router.post("/", summary="[Admin/Maintainer] Create a new Test")
def create_test(t: TestCreate, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.create_test(cursor, t, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.get("/", summary="Return all tests")
def get_all_tests(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return test_service.get_all_tests(cursor, current_user)


@router.get("/{test_id}", summary="Get Full Test Details & Contacts")
def get_test_details(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return test_service.get_test_details(cursor, test_id, current_user)


@router.put("/{test_id}", summary="[Admin/Maintainer] Update a specific test")
def update_test(test_id: str, t: TestBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.update_test(cursor, test_id, t, current_user, background_tasks)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/{test_id}", summary="[Admin/Maintainer] Delete a specific test")
def delete_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.delete_test(cursor, test_id, current_user, background_tasks)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.post("/bulk", summary="[Admin/Maintainer] bulk creation of tests")
def bulk_create_tests(req: BulkTestCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_maintainer_or_admin)):
    sl_id = str(current_user.get('service_lane_id')) if current_user.get('service_lane_id') else None
    background_tasks.add_task(test_service.process_bulk_tests_background, req.asset_ids, str(current_user['id']),
                              str(current_user['role']), sl_id)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Generating {len(req.asset_ids)} tests from active pool."}


@router.post("/{test_id}/workspace", summary="Create workspace on Google for each test")
def provision_workspace_manually(test_id: str, background_tasks: BackgroundTasks,
                                 current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return test_service.provision_workspace_manually(cursor, test_id, current_user, background_tasks)


@router.put("/{test_id}/tentative", summary="[Admin/Maintainer] Flag the test as Tentative")
def toggle_tentative(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.toggle_tentative(cursor, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/{test_id}/schedule", summary="[Admin/Maintainer] Schedule a test")
def schedule_test(test_id: str, schedule: TestSchedule, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.schedule_test(cursor, test_id, schedule, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/{test_id}/unschedule", summary="[Admin/Maintainer] Unschedule a test")
def unschedule_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.unschedule_test(cursor, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/{test_id}/complete", summary="[Admin/Maintainer] Flag a test as complete")
def complete_test(test_id: str, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.complete_test(cursor, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.put("/{test_id}/unable", summary="[Admin/Maintainer] Flag a test as unable")
def mark_test_unable(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.mark_test_unable(cursor, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/{test_id}/unstop", summary="[Admin/Maintainer] Roll back a unable test to normal")
def unstop_test(test_id: str, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.unstop_test(cursor, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/{test_id}/uncomplete", summary="[Admin/Maintainer] Make un-completing a test cleaner on the backend")
def uncomplete_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_maintainer_or_admin), cursor=Depends(get_db_cursor)):
    res = test_service.uncomplete_test(cursor, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.post("/assignments", summary="[Admin Only] Assigne a test to a pentester")
def create_assignment(assign: AssignmentCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = test_service.create_assignment(cursor, assign, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/assignments/{test_id}/{user_id}", summary="[Admin Only] Remove pentester from assigned test")
def remove_assignment(test_id: str, user_id: str, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = test_service.remove_assignment(cursor, test_id, user_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.get("/{test_id}/history", summary="Return the test history")
def get_test_history(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return test_service.get_test_history(cursor, test_id, current_user)


@router.get("/{test_id}/secret", summary="Return the encrypted test secret")
def get_test_secret(test_id: str, current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    return test_service.get_test_secret(cursor, test_id, current_user)


@router.put("/{test_id}/secret", summary="Update the test secret")
def update_test_secret(test_id: str, payload: dict, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    res = test_service.update_test_secret(cursor, test_id, payload, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/{test_id}/secret", summary="[Admin Only] Delete the test secret")
def delete_test_secret(test_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                       cursor=Depends(get_db_cursor)):
    res = test_service.delete_test_secret(cursor, test_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.post("/{test_id}/presentation", summary="Create a new presentation")
def trigger_presentation_generation(test_id: str, background_tasks: BackgroundTasks,
                                    current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') == 'read_only': raise HTTPException(status_code=403,
                                                                    detail="Read-only users cannot trigger generation.")

    where_clauses, params = ["t.id = %s"], [test_id]
    if current_user.get('role') == 'maintainer':
        where_clauses.append("t.service_lane_id = %s")
        params.append(str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    cursor.execute(
        f"SELECT t.name, t.kiss24, t.drive_folder_id, sl.name as service_name, ra.snow_number, t.start_week, t.start_year, t.duration_weeks FROM tests t LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id LEFT JOIN test_assets ta ON t.id = ta.test_id LEFT JOIN assets a ON ta.asset_id = a.id LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id WHERE {' AND '.join(where_clauses)} LIMIT 1",
        tuple(params))
    if not (row := cursor.fetchone()): raise HTTPException(status_code=404, detail="Test not found.")

    test_name, kiss24_id, drive_folder_id, service_name, snow_number, start_week, start_year, duration_weeks = row
    if not kiss24_id: raise HTTPException(status_code=400, detail="Missing kiss24 UUID.")
    if not drive_folder_id: raise HTTPException(status_code=400, detail="Missing Drive Workspace.")

    background_tasks.add_task(test_service.process_presentation_background, test_id, str(kiss24_id),
                              str(current_user["id"]), current_user["email"], str(current_user["role"]), test_name,
                              drive_folder_id, service_name, snow_number, start_week, start_year, duration_weeks)
    return {"message": "Presentation generation started in the background."}


@router.post("/{test_id}/report", summary="Generate PDF report")
def trigger_report_generation(test_id: str, background_tasks: BackgroundTasks,
                              current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') == 'read_only': raise HTTPException(status_code=403,
                                                                    detail="Read-only users cannot trigger generation.")

    where_clauses, params = ["t.id = %s"], [test_id]
    if current_user.get('role') == 'maintainer':
        where_clauses.append("t.service_lane_id = %s")
        params.append(str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    cursor.execute(
        f"SELECT t.name, t.kiss24, t.drive_folder_id, sl.display_order, t.start_week, t.start_year, t.duration_weeks FROM tests t LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id WHERE {' AND '.join(where_clauses)} LIMIT 1",
        tuple(params))
    if not (row := cursor.fetchone()): raise HTTPException(status_code=404, detail="Test not found.")

    test_name, kiss24_id, drive_folder_id, display_order, start_week, start_year, duration_weeks = row
    if not kiss24_id: raise HTTPException(status_code=400, detail="Missing kiss24 UUID.")
    if not drive_folder_id: raise HTTPException(status_code=400, detail="Missing Drive Workspace.")

    background_tasks.add_task(test_service.process_report_background, test_id, str(kiss24_id), str(current_user["id"]),
                              current_user["email"], str(current_user["role"]), test_name, drive_folder_id,
                              display_order if display_order is not None else 99, start_week, start_year,
                              duration_weeks)
    return {"message": "Report generation started in the background."}


@router.post("/{test_id}/vulnerabilities/report", summary="Generate Specific Vuln PDFs")
def trigger_vuln_reports(test_id: str, payload: dict, background_tasks: BackgroundTasks,
                         current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') == 'read_only': raise HTTPException(status_code=403,
                                                                    detail="Read-only users cannot trigger generation.")
    if not (vuln_uuids := payload.get("vuln_uuids", [])): raise HTTPException(status_code=400,
                                                                              detail="No vulnerabilities selected.")

    where_clauses, params = ["t.id = %s"], [test_id]
    if current_user.get('role') == 'maintainer':
        where_clauses.append("t.service_lane_id = %s")
        params.append(str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    cursor.execute(
        f"SELECT t.name, t.kiss24, t.drive_folder_id, sl.display_order FROM tests t LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id WHERE {' AND '.join(where_clauses)} LIMIT 1",
        tuple(params))
    if not (row := cursor.fetchone()): raise HTTPException(status_code=404, detail="Test not found.")

    test_name, kiss24_id, drive_folder_id, display_order = row
    if not kiss24_id: raise HTTPException(status_code=400, detail="Missing kiss24 UUID.")
    if not drive_folder_id: raise HTTPException(status_code=400, detail="Missing Drive Workspace.")

    background_tasks.add_task(test_service.process_vuln_report_background, test_id, str(kiss24_id),
                              str(current_user["id"]), current_user["email"], str(current_user["role"]), test_name,
                              drive_folder_id, display_order if display_order is not None else 99, vuln_uuids)
    return {"message": f"Generating {len(vuln_uuids)} report(s) in the background!"}


@router.get("/{test_id}/analysis", summary="Get Analysis report")
def get_test_analysis(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') not in ['admin', 'pentester', 'read_only']: raise HTTPException(status_code=403,
                                                                                                detail="Access denied.")
    cursor.execute("SELECT status, analysis_text, timestamp FROM test_analyses WHERE test_id = %s", (test_id,))
    if not (row := cursor.fetchone()): raise HTTPException(status_code=404, detail="No analysis found.")
    return {"status": row[0], "analysis_text": row[1], "timestamp": row[2]}


@router.post("/{test_id}/analysis", summary="Perform vulnerabilities analysis")
def trigger_test_analysis(test_id: str, background_tasks: BackgroundTasks,
                          current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') not in ['admin', 'pentester']: raise HTTPException(status_code=403,
                                                                                   detail="Access denied.")
    cursor.execute("SELECT name, kiss24 FROM tests WHERE id = %s", (test_id,))
    if not (row := cursor.fetchone()) or not row[1]: raise HTTPException(status_code=400, detail="Missing Kiss24 UUID.")

    cursor.execute(
        "INSERT INTO test_analyses (test_id, status, timestamp) VALUES (%s, 'PENDING', CURRENT_TIMESTAMP) ON CONFLICT (test_id) DO UPDATE SET status = 'PENDING', analysis_text = NULL, timestamp = CURRENT_TIMESTAMP",
        (test_id,))
    cursor.connection.commit()
    background_tasks.add_task(test_service.process_vuln_analysis_background, test_id, str(row[1]),
                              str(current_user["id"]), current_user["email"], row[0])
    return {"message": "Analysis started in the background."}


@router.get("/{test_id}/milestones", summary="Get Milestones test")
def get_milestones(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return test_service.get_milestones(cursor, test_id, current_user)


@router.put("/{test_id}/milestones", summary="Update Milestones test")
def update_milestone(test_id: str, payload: MilestoneUpdate, current_user: dict = Depends(require_write_access),
                     cursor=Depends(get_db_cursor)):
    return test_service.update_milestone(cursor, test_id, payload, current_user)


@router.get("/{test_id}/requirements", summary="Get Requirement test")
def get_requirements(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return test_service.get_requirements(cursor, test_id, current_user)


@router.post("/{test_id}/requirements", summary="Add Requirement test")
def add_requirement(test_id: str, req: RequirementCreate, current_user: dict = Depends(require_write_access),
                    cursor=Depends(get_db_cursor)):
    return test_service.add_requirement(cursor, test_id, req, current_user)


@router.delete("/requirements/{req_id}", summary="Delete Requirement test")
def delete_requirement(req_id: str, current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    return test_service.delete_requirement(cursor, req_id, current_user)


@router.put("/requirements/{req_id}/toggle", summary="Edit Requirement test")
def toggle_requirement(req_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    return test_service.toggle_requirement(cursor, req_id, current_user)