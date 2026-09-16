import uuid
import os
import json
import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from database import db_cursor_context
from routers.auth import verify_lane_access
from websockets_manager import manager
from audit_logger import log_audit_event
from utils.drive_manager import DriveManager, background_archive_workspace, background_provision_workspace, background_relocate_workspace
from utils.secret_manager import get_secret
from utils.vuln_analysis import build_payload, run_cloud_run_analysis
from system_services .rag_service import process_test_documents_background
from presentations.presentation import generate_presentation
from reports import osrgt_v3, pdf_gen
from utils.kiss24_service import validate_kiss24_findings, get_vuln_fields_map, fetch_all_kiss24, get_report_type_id

FRONTEND_TO_DB_STAGES = {
    "Not Planned": "NOT_PLANNED", "Scheduled": "SCHEDULED", "In Progress": "IN_PROGRESS",
    "Stopped": "STOPPED", "Deleted": "DELETED", "Completed": "COMPLETED", "Archived": "ARCHIVED"
}
BASE_URL = str(os.environ.get("FRONTEND_URL"))


def log_test_history(cursor, test_id: str, user_id: str, action: str, details: str = None):
    new_test_hist_id = str(uuid.uuid4())
    cursor.execute(
        'INSERT INTO test_history (id, test_id, user_id, action, details, timestamp) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)',
        (new_test_hist_id, test_id, str(user_id) if user_id else None, action, details))
    cursor.execute(
        'SELECT a.raw_asset_id, t.name FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN tests t ON ta.test_id = t.id WHERE ta.test_id = %s',
        (test_id,))
    for raw_asset_id, test_name in cursor.fetchall():
        cursor.execute(
            'INSERT INTO asset_history (id, raw_asset_id, user_id, action, details, timestamp) VALUES (%s, %s, %s, %s, %s, CURRENT_TIMESTAMP)',
            (str(uuid.uuid4()), str(raw_asset_id), str(user_id) if user_id else None, action,
             f"[Test: {test_name}] {details}" if details else f"[Test: {test_name}] Status updated to {action}."))


# --- BACKGROUND TASKS ---
async def process_presentation_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, user_role: str,
                                          test_name: str, drive_folder_id: str, service_name: str, snow_number: str,
                                          start_week: int, start_year: int, duration_weeks: float):
    try:
        data = await asyncio.to_thread(generate_presentation, kiss24_id, drive_folder_id, service_name, snow_number,
                                       start_week, start_year, duration_weeks)
        if data.get("fileId") and data.get("fileName"):
            with db_cursor_context() as cursor:
                cursor.execute(
                    "INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, doc_type, last_modified, synced_at) VALUES (gen_random_uuid(), %s, %s, %s, 'application/vnd.openxmlformats-officedocument.presentationml.presentation', %s, 'PRESENTATION', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (drive_file_id) DO UPDATE SET last_modified = CURRENT_TIMESTAMP, synced_at = CURRENT_TIMESTAMP",
                    (test_id, data.get("fileId"), data.get("fileName"), data.get("driveLink", "")))
                cursor.execute(
                    "INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, 'Generate Presentation', true) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true",
                    (test_id,))
                cursor.connection.commit()
            try:
                await asyncio.to_thread(process_test_documents_background, test_id, user_id, user_role)
            except Exception as rag_err:
                print(f"RAG warning: {rag_err}")

        issues = [f"{k.capitalize()}: {v.get('reason')}" for k, v in data.get("warnings", {}).items() if
                  isinstance(v, dict) and not v.get("healthy")]
        issues_text = "\n\n[!] Warnings:\n- " + "\n- ".join(issues) if issues else "\n\n[+] Health Check: 100% Healthy"
        message, notif_type, ws_action = f"Presentation for '{test_name}' is ready!\nLink: {data.get('driveLink')}{issues_text}", "SUCCESS", "PRESENTATION_READY"
    except Exception as e:
        message, notif_type, ws_action = f"Generation failed for '{test_name}'. Error: {str(e)}", "ERROR", "PRESENTATION_FAILED"

    await manager.broadcast(json.dumps({"action": ws_action, "email": user_email, "message": message}))
    with db_cursor_context() as cursor:
        cursor.execute(
            "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
            (str(uuid.uuid4()), user_id, message, notif_type))
        cursor.connection.commit()
    await manager.broadcast('{"action": "REFRESH_BOARD"}')


async def process_report_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, user_role: str,
                                    test_name: str, drive_folder_id: str, display_order: int, start_week: int,
                                    start_year: int, duration_weeks: float):
    try:
        start_date_str = end_date_str = None
        try:
            test_start = datetime.fromisocalendar(start_year, start_week, 1)
            end_date_str = (test_start + timedelta(days=(max(1, int(duration_weeks or 1)) - 1) * 7 + 4)).strftime(
                "%d-%m-%Y")
            start_date_str = test_start.strftime("%d-%m-%Y")
        except:
            pass

        api_key = (get_secret(os.environ.get("KISS_24_API_KEY_NAME")) or "").strip()
        report_type = get_report_type_id(display_order)

        vulns = await asyncio.to_thread(fetch_all_kiss24, 'vulnerabilities', api_key, {"tests": [kiss24_id]})
        vuln_fields_map = await asyncio.to_thread(get_vuln_fields_map, [v['uuid'] for v in vulns], api_key)
        if invalid_findings := await asyncio.to_thread(validate_kiss24_findings, vulns, vuln_fields_map, report_type,
                                                       api_key):
            raise ValueError(f"Report aborted for '{test_name}'. Validation failed:\n" + "".join(
                [f"\n- Vuln {f['vuln_uuid']}:\n  " + "\n  ".join(f['reasons']) for f in invalid_findings]))

        report_args = {"pentest": kiss24_id, "type": report_type, "api_key": api_key, "action": "generate",
                       "minify": False, "environment": "sec24prd", "loglevel": "info", "devoteam": False,
                       "start": start_date_str, "end": end_date_str, "custom_fields": vuln_fields_map}
        html_content, html_filename = await asyncio.to_thread(osrgt_v3.generate_html_report, report_args)
        pdf_content, pdf_filename = await asyncio.to_thread(pdf_gen.convert_html_to_pdf, html_content, html_filename)

        drive_manager = DriveManager()
        await asyncio.to_thread(drive_manager.upload_file, drive_folder_id, html_filename, html_content.encode('utf-8'),
                                'text/html')
        pdf_result = await asyncio.to_thread(drive_manager.upload_file, drive_folder_id, pdf_filename, pdf_content,
                                             'application/pdf')

        with db_cursor_context() as cursor:
            cursor.execute(
                "INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, doc_type, last_modified, synced_at) VALUES (gen_random_uuid(), %s, %s, %s, 'application/pdf', %s, 'FULL_TEST_REPORT', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (drive_file_id) DO UPDATE SET last_modified = CURRENT_TIMESTAMP, synced_at = CURRENT_TIMESTAMP",
                (test_id, pdf_result["id"], pdf_filename, pdf_result["link"]))
            cursor.execute(
                "INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, 'Generate Report PDF', true) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true",
                (test_id,))
            cursor.connection.commit()

        try:
            await asyncio.to_thread(process_test_documents_background, test_id, user_id, user_role)
        except Exception:
            pass

        message = f"Report for '{test_name}' is ready!\nPDF Link: {pdf_result['link']}"
        await manager.broadcast(json.dumps({"action": "REPORT_READY", "email": user_email, "message": message}))
        with db_cursor_context() as cursor:
            cursor.execute(
                "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), user_id, message, "SUCCESS"))
            cursor.connection.commit()
        await asyncio.to_thread(log_audit_event, user_id=user_id, role=user_role, action="REPORT_GENERATION_SUCCESS",
                                resource_type="REPORTING", resource_id=test_id,
                                details=f"Generated PDF for '{test_name}'.")

    except Exception as e:
        error_details = str(e)
        user_message = error_details if isinstance(e, ValueError) and (
                    "Validation failed" in error_details or "API Error" in error_details) else f"Report generation failed for '{test_name}'."
        await manager.broadcast(json.dumps({"action": "REPORT_FAILED", "email": user_email, "message": user_message}))
        with db_cursor_context() as cursor:
            cursor.execute(
                "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), user_id, user_message, "ERROR"))
            cursor.connection.commit()
        await asyncio.to_thread(log_audit_event, user_id=user_id, role=user_role, action="REPORT_GENERATION_CRASH",
                                resource_type="REPORTING", resource_id=test_id,
                                details=f"Crash: {error_details}\nTrace: {traceback.format_exc()}")
    await manager.broadcast('{"action": "REFRESH_BOARD"}')


async def process_vuln_report_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, user_role: str,
                                         test_name: str, drive_folder_id: str, display_order: int, vuln_uuids: list):
    try:
        api_key = (get_secret(os.environ.get("KISS_24_API_KEY_NAME")) or "").strip()
        report_args = {"pentest": kiss24_id, "vuln": vuln_uuids, "type": get_report_type_id(display_order),
                       "api_key": api_key, "action": "generate", "minify": False, "environment": "sec24prd",
                       "loglevel": "info", "devoteam": False}
        reports_data = await asyncio.to_thread(osrgt_v3.generate_html_report, report_args)

        drive_manager = DriveManager()
        uploaded_count, generated_links = 0, []

        with db_cursor_context() as cursor:
            for html_content, html_filename in reports_data:
                pdf_content, pdf_filename = await asyncio.to_thread(pdf_gen.convert_html_to_pdf, html_content,
                                                                    html_filename)
                pdf_result = await asyncio.to_thread(drive_manager.upload_file, drive_folder_id, pdf_filename,
                                                     pdf_content, 'application/pdf')
                cursor.execute(
                    "INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, doc_type, last_modified, synced_at) VALUES (gen_random_uuid(), %s, %s, %s, 'application/pdf', %s, 'VULN_REPORT', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) ON CONFLICT (drive_file_id) DO UPDATE SET last_modified = CURRENT_TIMESTAMP, synced_at = CURRENT_TIMESTAMP",
                    (test_id, pdf_result["id"], pdf_filename, pdf_result["link"]))
                uploaded_count += 1
                generated_links.append((pdf_filename, pdf_result["link"]))
            cursor.connection.commit()

        try:
            await asyncio.to_thread(process_test_documents_background, test_id, user_id, user_role)
        except Exception:
            pass

        message = f"Successfully generated {uploaded_count} vuln report(s) for '{test_name}':\n" + "".join(
            [f"• {n}\n  Link: {l}\n" for n, l in generated_links])
        with db_cursor_context() as cursor:
            cursor.execute(
                "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), user_id, message, "SUCCESS"))
            cursor.connection.commit()

        await asyncio.to_thread(log_audit_event, user_id=user_id, role=user_role,
                                action="VULN_REPORT_GENERATION_SUCCESS", resource_type="REPORTING", resource_id=test_id,
                                details=f"Generated {uploaded_count} individual vuln reports.")
        await manager.broadcast(json.dumps({"action": "REPORT_READY", "email": user_email, "message": message}))
    except Exception as e:
        user_message = f"Vuln Report generation failed for '{test_name}': {str(e)}"
        with db_cursor_context() as cursor:
            cursor.execute(
                "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), user_id, user_message, "ERROR"))
            cursor.connection.commit()
        await asyncio.to_thread(log_audit_event, user_id=user_id, role=user_role, action="VULN_REPORT_GENERATION_CRASH",
                                resource_type="REPORTING", resource_id=test_id, details=str(e))
        await manager.broadcast(json.dumps({"action": "REPORT_FAILED", "email": user_email, "message": user_message}))
    await manager.broadcast('{"action": "REFRESH_BOARD"}')


async def process_vuln_analysis_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, test_name: str):
    try:
        payload = await build_payload(kiss24_id)
        if not payload or not payload.get("vulnerabilities"): raise ValueError("No vulnerabilities found.")
        analysis_response = await run_cloud_run_analysis(payload)
        stitched_markdown = "\n\n---\n\n".join(
            [r.get("analysis", "") for r in analysis_response.get("results", []) if r.get("status") == "success"])
        if not stitched_markdown: raise ValueError("Cloud Run returned no valid text.")

        with db_cursor_context() as cursor:
            cursor.execute(
                "UPDATE test_analyses SET status = 'COMPLETED', analysis_text = %s, timestamp = CURRENT_TIMESTAMP WHERE test_id = %s",
                (stitched_markdown, test_id))
            cursor.execute(
                "INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, doc_type, last_modified, synced_at, is_virtual) VALUES (gen_random_uuid(), %s, %s, %s, 'text/markdown', %s, 'LLM_ANALYSIS', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, TRUE) ON CONFLICT (drive_file_id) DO UPDATE SET file_name = EXCLUDED.file_name, last_modified = CURRENT_TIMESTAMP, synced_at = CURRENT_TIMESTAMP",
                (test_id, f"analysis_{test_id}", f"LLM_Vulnerability_Analysis_{test_name}.md",
                 f"{BASE_URL}/tests/{test_id}/analysis"))
            cursor.execute(
                "INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, 'Validate Finding', true) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true",
                (test_id,))
            cursor.connection.commit()

        try:
            await asyncio.to_thread(process_test_documents_background, test_id, user_id, "admin")
        except Exception:
            pass

        with db_cursor_context() as cursor:
            cursor.execute(
                "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), user_id, f"Analysis for '{test_name}' is ready!", "SUCCESS"))
            cursor.connection.commit()
        await manager.broadcast(json.dumps(
            {"action": "REPORT_READY", "email": user_email, "message": f"Analysis ready!",
             "link": f"/tests/{test_id}/analysis"}))
    except Exception as e:
        with db_cursor_context() as cursor:
            cursor.execute(
                "UPDATE test_analyses SET status = 'FAILED', timestamp = CURRENT_TIMESTAMP WHERE test_id = %s",
                (test_id,))
            cursor.connection.commit()
        await manager.broadcast(
            json.dumps({"action": "REPORT_FAILED", "email": user_email, "message": f"Analysis failed: {str(e)}"}))


def process_bulk_tests_background(asset_ids, user_id: str, role: str, service_lane_id: str = None):
    tests_to_provision = []
    with db_cursor_context() as cursor:
        for asset_id in asset_ids:
            query = "SELECT r.name, r.service_forecast_id, s.default_credits, s.default_duration_weeks, s.name as service_name, c.name as country_name, s.auto_provision_workspace, r.category_id FROM assets a JOIN raw_assets r ON a.raw_asset_id = r.id LEFT JOIN services_lanes s ON r.service_forecast_id = s.id LEFT JOIN countries c ON r.country_id = c.id WHERE a.id = %s"
            params = [str(asset_id)]
            if role == 'maintainer':
                query += " AND r.service_forecast_id = %s"
                params.append(str(service_lane_id) if service_lane_id else '00000000-0000-0000-0000-000000000000')
            query += " AND (r.duplicate_allowed = TRUE OR NOT EXISTS (SELECT 1 FROM test_assets ta JOIN tests t ON ta.test_id = t.id WHERE ta.asset_id = a.id AND t.stages::text IN ('NOT_PLANNED', 'SCHEDULED', 'IN_PROGRESS')))"

            cursor.execute(query, tuple(params))
            asset_data = cursor.fetchone()
            if not asset_data or not asset_data[1]: continue

            asset_name, asset_service_lane_id, def_credits, def_duration, service_name, country_name, auto_provision, cat_id = asset_data
            new_test_id = str(uuid.uuid4())
            cursor.execute(
                "INSERT INTO tests (id, name, service_lane_id, category_id, credits_per_week, duration_weeks, stages) VALUES (%s, %s, %s, %s, %s, %s, 'NOT_PLANNED') RETURNING id",
                (new_test_id, asset_name, str(asset_service_lane_id), str(cat_id) if cat_id else None,
                 float(def_credits or 2.0), int(def_duration or 1)))
            cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_test_id, str(asset_id)))

            log_test_history(cursor, new_test_id, user_id, "GENERATED", f"Test generated from Asset Pool.")
            log_audit_event(user_id=user_id, role=role, action="TEST_CREATED", resource_type="TESTS",
                            resource_id=new_test_id, details=f"Bulk created test for {asset_name}.")
            tests_to_provision.append(
                (new_test_id, datetime.now().year, service_name, country_name, asset_name, auto_provision))
        cursor.connection.commit()

    for test_id, year, s_name, c_name, t_name, auto_prov in tests_to_provision:
        if auto_prov: DriveManager().provision_test_workspace(test_id, year, s_name, c_name, t_name)


# --- ENDPOINTS LOGIC ---
def create_test(cursor, t, current_user: dict):
    verify_lane_access(current_user, str(t.service_lane_id))
    new_test_id, cat_id = str(uuid.uuid4()), str(t.category_id) if t.category_id else None
    cursor.execute(
        "INSERT INTO tests (id, name, service_lane_id, category_id, credits_per_week, duration_weeks, stages) VALUES (%s, %s, %s, %s, %s, %s, 'NOT_PLANNED') RETURNING id",
        (new_test_id, t.name, str(t.service_lane_id), cat_id, t.credits_per_week, t.duration_weeks))
    for asset_id in t.asset_ids:
        cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_test_id, str(asset_id)))
    log_test_history(cursor, new_test_id, current_user['id'], "CREATED", "Test manually created.")
    cursor.connection.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_CREATED", "TESTS", new_test_id,
                    f"Test {t.name} created.")
    return {"message": "Test created successfully", "id": new_test_id}


def get_all_tests(cursor, current_user: dict):
    where_clauses, params = [], []
    if current_user.get('role') == 'maintainer':
        where_clauses.append("t.service_lane_id = %s")
        params.append(str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))
    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cursor.execute(f'''
        SELECT t.id, t.name, t.start_week, t.start_year, t.duration_weeks, t.stages::text as status,
            s.name as service_lane_name, s.is_active as is_service_active, s.auto_provision_workspace, sc.name as category_name, 
            COALESCE((SELECT string_agg(DISTINCT u.name, ', ') FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = t.id), 'Unassigned') as assigned_pentesters,
            EXISTS(SELECT 1 FROM secret_notes WHERE test_id = t.id) as has_secret, t.drive_folder_url, t.kiss24,
            (SELECT a.raw_asset_id FROM test_assets ta JOIN assets a ON ta.asset_id = a.id WHERE ta.test_id = t.id LIMIT 1) as raw_asset_id,
            (SELECT ra.is_kpi FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN raw_assets ra ON a.raw_asset_id = ra.id WHERE ta.test_id = t.id LIMIT 1) as is_kpi,
            (SELECT ra.is_critical FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN raw_assets ra ON a.raw_asset_id = ra.id WHERE ta.test_id = t.id LIMIT 1) as is_critical,
            (SELECT at.name FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN raw_assets ra ON a.raw_asset_id = ra.id JOIN asset_types at ON ra.asset_type_id = at.id WHERE ta.test_id = t.id LIMIT 1) as asset_type_name
        FROM tests t LEFT JOIN services_lanes s ON t.service_lane_id = s.id LEFT JOIN service_categories sc ON t.category_id = sc.id {where_str}
        ORDER BY t.start_year DESC NULLS LAST, t.start_week DESC NULLS LAST, t.name ASC
    ''', tuple(params))
    return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]


def get_test_details(cursor, test_id: str, current_user: dict):
    where_clauses, params = ["t.id = %s"], [test_id]
    if current_user.get('role') == 'maintainer':
        where_clauses.append("t.service_lane_id = %s")
        params.append(str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    cursor.execute(f'''
        SELECT t.id, t.name, t.service_lane_id, t.credits_per_week, t.duration_weeks, t.stages::text as status, t.start_week, t.start_year, 
               t.is_tentative, t.kiss24, t.drive_folder_id, t.drive_folder_url, s.name as service_lane_name, s.auto_provision_workspace, ct.kiss24_uuid as country_kiss24_uuid,
               EXISTS(SELECT 1 FROM secret_notes WHERE test_id = t.id) as has_secret,
               COALESCE((SELECT string_agg(DISTINCT u.name, ', ') FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = t.id), 'Unassigned') as assigned_pentesters,
               ra.category_id, c.name as category_name
        FROM tests t LEFT JOIN services_lanes s ON t.service_lane_id = s.id LEFT JOIN test_assets ta ON t.id = ta.test_id LEFT JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id LEFT JOIN service_categories c ON ra.category_id = c.id LEFT JOIN countries ct ON ra.country_id = ct.id
        WHERE {" AND ".join(where_clauses)} LIMIT 1
    ''', tuple(params))
    test_row = cursor.fetchone()
    if not test_row: raise HTTPException(status_code=404, detail="Test not found")

    test_data = dict(zip([desc[0] for desc in cursor.description], test_row))

    cursor.execute(
        'SELECT a.id as asset_id, a.raw_asset_id, r.name as asset_name, r.country_id, r.kiss24_asset_id FROM test_assets ta JOIN assets a ON ta.asset_id = a.id JOIN raw_assets r ON a.raw_asset_id = r.id WHERE ta.test_id = %s',
        (test_id,))
    test_data["assets"] = [dict(zip([desc[0] for desc in cursor.description], row)) for row in cursor.fetchall()]

    raw_asset_ids = [a['raw_asset_id'] for a in test_data["assets"] if a['raw_asset_id']]
    country_ids = list(set([a['country_id'] for a in test_data["assets"] if a['country_id']]))

    test_data["asset_contacts"] = []
    if raw_asset_ids:
        cursor.execute(
            f"SELECT DISTINCT c.id as contact_id, c.email, c.full_name, rac.is_stakeholder, rac.is_developer FROM raw_asset_contacts rac JOIN contacts c ON rac.contact_id = c.id WHERE rac.raw_asset_id IN ({','.join(['%s'] * len(raw_asset_ids))}) ORDER BY c.email ASC",
            tuple(raw_asset_ids))
        test_data["asset_contacts"] = [dict(zip([desc[0] for desc in cursor.description], row)) for row in
                                       cursor.fetchall()]

    test_data["country_contacts"] = []
    if country_ids:
        cursor.execute(
            f"SELECT DISTINCT c.id as contact_id, c.email, c.full_name, cc.is_stakeholder, cc.is_developer FROM country_contacts cc JOIN contacts c ON cc.contact_id = c.id WHERE cc.country_id IN ({','.join(['%s'] * len(country_ids))}) ORDER BY c.email ASC",
            tuple(country_ids))
        test_data["country_contacts"] = [dict(zip([desc[0] for desc in cursor.description], row)) for row in
                                         cursor.fetchall()]

    cursor.execute(
        'SELECT th.id, th.action, th.details, th.timestamp, u.name as user_name FROM test_history th LEFT JOIN users u ON th.user_id = u.id WHERE th.test_id = %s ORDER BY th.timestamp DESC',
        (test_id,))
    test_data["history"] = [dict(zip([desc[0] for desc in cursor.description], row)) for row in cursor.fetchall()]
    return test_data


def update_test(cursor, test_id: str, t, current_user: dict, background_tasks):
    verify_lane_access(current_user, str(t.service_lane_id))
    cursor.execute(
        'SELECT t.drive_folder_id, s.name, c.name, t.start_year FROM tests t LEFT JOIN services_lanes s ON t.service_lane_id = s.id LEFT JOIN test_assets ta ON t.id = ta.test_id LEFT JOIN assets a ON ta.asset_id = a.id LEFT JOIN countries c ON a.country_id = c.id WHERE t.id = %s LIMIT 1',
        (test_id,))
    old_data = cursor.fetchone()

    db_stage = FRONTEND_TO_DB_STAGES.get(t.status, "NOT_PLANNED")
    if db_stage == 'NOT_PLANNED':
        cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
        cursor.execute('UPDATE tests SET start_week = NULL, start_year = NULL WHERE id = %s', (test_id,))

    cat_id = str(t.category_id) if hasattr(t, 'category_id') and t.category_id else None
    kiss24_val = str(t.kiss24) if hasattr(t, 'kiss24') and t.kiss24 else None

    cursor.execute(
        'UPDATE tests SET name=%s, service_lane_id=%s, category_id=%s, credits_per_week=%s, duration_weeks=%s, stages=%s, is_tentative=%s, kiss24=%s WHERE id=%s',
        (t.name, str(t.service_lane_id), cat_id, t.credits_per_week, t.duration_weeks, db_stage, t.is_tentative,
         kiss24_val, test_id))
    cursor.execute(
        'UPDATE raw_assets SET category_id = %s WHERE id IN (SELECT a.raw_asset_id FROM test_assets ta JOIN assets a ON ta.asset_id = a.id WHERE ta.test_id = %s)',
        (cat_id, test_id))

    log_test_history(cursor, test_id, current_user['id'], "UPDATED",
                     f"Settings updated: {t.credits_per_week}cr, {t.duration_weeks}wks.")
    cursor.connection.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_UPDATED", "TESTS", test_id, "Updated.")

    if old_data and old_data[0]:
        cursor.execute("SELECT name FROM services_lanes WHERE id = %s", (str(t.service_lane_id),))
        background_tasks.add_task(background_relocate_workspace, old_data[0],
                                  t.start_year or old_data[3] or datetime.now().year, cursor.fetchone()[0],
                                  old_data[2] or "General", t.name)
    return {"message": "Test updated successfully."}


def delete_test(cursor, test_id: str, current_user: dict, background_tasks):
    cursor.execute("SELECT name, drive_folder_id, service_lane_id FROM tests WHERE id = %s", (test_id,))
    test_data = cursor.fetchone()
    if not test_data: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test_data[2]))

    log_test_history(cursor, test_id, current_user['id'], "DELETED", "Test permanently deleted and assets freed.")
    cursor.execute('DELETE FROM test_assets WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('DELETE FROM tests WHERE id = %s', (test_id,))
    cursor.connection.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_DELETED", "TESTS", test_id, "Deleted.")
    if test_data and test_data[1]: background_tasks.add_task(background_archive_workspace, test_data[1], test_data[0])
    return {"message": "Test permanently deleted and assets freed."}


def provision_workspace_manually(cursor, test_id: str, current_user: dict, background_tasks):
    where_clauses, params = ["t.id = %s"], [test_id]
    if current_user.get('role') == 'maintainer':
        where_clauses.append("t.service_lane_id = %s")
        params.append(str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    cursor.execute(
        f"SELECT t.name, s.name, c.name, t.start_year FROM tests t LEFT JOIN services_lanes s ON t.service_lane_id = s.id LEFT JOIN test_assets ta ON t.id = ta.test_id LEFT JOIN assets a ON ta.asset_id = a.id LEFT JOIN countries c ON a.country_id = c.id WHERE {' AND '.join(where_clauses)} LIMIT 1",
        tuple(params))
    test_data = cursor.fetchone()
    if not test_data: raise HTTPException(status_code=404, detail="Test not found.")

    background_tasks.add_task(background_provision_workspace, test_id, test_data[3] or datetime.now().year,
                              test_data[1], test_data[2], test_data[0])
    log_audit_event(str(current_user["id"]), current_user["role"], "PROVISIONING_WORKSPACE", "TESTS", test_id,
                    "Provisioned.")
    return {"message": "Workspace provisioning started."}


def toggle_tentative(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    test_data = cursor.fetchone()
    if not test_data: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test_data[0]))

    cursor.execute("UPDATE tests SET is_tentative = NOT is_tentative WHERE id = %s", (test_id,))
    cursor.execute("SELECT is_tentative FROM tests WHERE id = %s", (test_id,))
    state_str = "Marked as Tentative (TBC)" if cursor.fetchone()[0] else "Removed Tentative mark"
    log_test_history(cursor, test_id, current_user['id'], "UPDATED", state_str)
    cursor.connection.commit()
    return {"message": state_str}


def schedule_test(cursor, test_id: str, schedule, current_user: dict):
    cursor.execute('SELECT start_week, start_year, name, service_lane_id FROM tests WHERE id = %s', (test_id,))
    test_row = cursor.fetchone()
    if not test_row: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test_row[3]))

    old_week, old_year, test_name, _ = test_row
    if old_week is not None and old_year is not None and (
            old_week != schedule.start_week or old_year != schedule.start_year):
        cursor.execute('SELECT DISTINCT user_id FROM assignments WHERE test_id = %s', (test_id,))
        for (u_id,) in cursor.fetchall():
            cursor.execute(
                "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), str(u_id), f"Removed from {test_name} (rescheduled).", "REMOVAL"))
        cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
        log_test_history(cursor, test_id, current_user['id'], "UNASSIGNED", "Pentesters removed due to schedule shift.")

    cursor.execute('UPDATE tests SET start_week = %s, start_year = %s, stages = %s WHERE id = %s',
                   (schedule.start_week, schedule.start_year, "SCHEDULED", test_id))
    log_test_history(cursor, test_id, current_user['id'], "SCHEDULED",
                     f"Scheduled Wk {schedule.start_week}, {schedule.start_year}.")
    cursor.connection.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_SCHEDULED", "TESTS", test_id, "Scheduled.")
    return {"message": "Test scheduled on the board."}


def unschedule_test(cursor, test_id: str, current_user: dict):
    cursor.execute('SELECT user_id FROM assignments WHERE test_id = %s', (test_id,))
    assigned_users = cursor.fetchall()
    cursor.execute("SELECT name, service_lane_id FROM tests WHERE id = %s", (test_id,))
    test_row = cursor.fetchone()
    if not test_row: raise HTTPException(status_code=404, detail="Test not found.")
    verify_lane_access(current_user, str(test_row[1]))

    for (user_id,) in assigned_users:
        cursor.execute(
            "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
            (str(uuid.uuid4()), str(user_id), f"Removed from {test_row[0]} (unscheduled).", "REMOVAL"))

    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
    cursor.execute('UPDATE tests SET start_week = NULL, start_year = NULL, stages = %s WHERE id = %s',
                   ("NOT_PLANNED", test_id))
    log_test_history(cursor, test_id, current_user['id'], "UNSCHEDULED", "Returned to backlog.")
    cursor.connection.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_UNSCHEDULED", "TESTS", test_id, "Unscheduled.")
    return {"message": "Test returned to backlog."}


def complete_test(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    test_data = cursor.fetchone()
    if not test_data: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test_data[0]))

    cursor.execute("UPDATE tests SET stages = 'COMPLETED' WHERE id = %s", (test_id,))
    log_test_history(cursor, test_id, current_user['id'], "COMPLETED", "Marked as completed.")
    cursor.connection.commit()
    return {"message": "Test marked as Completed."}


def mark_test_unable(cursor, test_id: str, current_user: dict):
    cursor.execute('SELECT name, service_lane_id, credits_per_week, duration_weeks FROM tests WHERE id = %s',
                   (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Test not found.")
    verify_lane_access(current_user, str(row[1]))

    cursor.execute("UPDATE tests SET stages = 'STOPPED', name = %s WHERE id = %s", (f"[BLOCKED] {row[0]}", test_id))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))

    clone_id = str(uuid.uuid4())
    cursor.execute(
        'INSERT INTO tests (id, name, service_lane_id, credits_per_week, duration_weeks, stages) VALUES (%s, %s, %s, %s, %s, %s)',
        (clone_id, row[0], str(row[1]), row[2], row[3], 'NOT_PLANNED'))

    cursor.execute('SELECT asset_id FROM test_assets WHERE test_id = %s', (test_id,))
    for (asset_id,) in cursor.fetchall(): cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)',
                                                         (clone_id, str(asset_id)))

    cursor.execute("SELECT user_id, action, details, timestamp FROM test_history WHERE test_id = %s", (test_id,))
    for h_user, h_action, h_details, h_time in cursor.fetchall():
        cursor.execute(
            'INSERT INTO test_history (id, test_id, user_id, action, details, timestamp) VALUES (%s, %s, %s, %s, %s, %s)',
            (str(uuid.uuid4()), clone_id, str(h_user) if h_user else None, h_action, h_details, h_time))

    log_test_history(cursor, clone_id, current_user['id'], "CLONED", "Resumed in backlog.")
    log_test_history(cursor, test_id, current_user['id'], "STOPPED", f"Clone generated: {clone_id}")
    cursor.connection.commit()
    return {"message": "Test marked as Stopped."}


def unstop_test(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT name, service_lane_id FROM tests WHERE id = %s AND stages = 'STOPPED'", (test_id,))
    row = cursor.fetchone()
    if not row: raise HTTPException(status_code=404, detail="Stopped test not found.")
    verify_lane_access(current_user, str(row[1]))

    original_name = row[0].replace("[BLOCKED] ", "") if row[0].startswith("[BLOCKED] ") else row[0]
    cursor.execute(
        "SELECT details FROM test_history WHERE test_id = %s AND action = 'STOPPED' ORDER BY timestamp DESC LIMIT 1",
        (test_id,))
    hist_row = cursor.fetchone()

    if hist_row and "Clone generated in backlog: " in hist_row[0]:
        clone_id = hist_row[0].split("Clone generated in backlog: ")[1].strip()
        cursor.execute("SELECT stages FROM tests WHERE id = %s", (clone_id,))
        if clone_stage_row := cursor.fetchone():
            if clone_stage_row[0] == 'NOT_PLANNED':
                cursor.execute("DELETE FROM test_assets WHERE test_id = %s", (clone_id,))
                cursor.execute("DELETE FROM tests WHERE id = %s", (clone_id,))
            else:
                raise HTTPException(status_code=400, detail="Cannot Undo Stop: The clone is already scheduled.")

    cursor.execute("UPDATE tests SET name = %s, stages = 'SCHEDULED' WHERE id = %s", (original_name, test_id))
    log_test_history(cursor, test_id, current_user['id'], "UNSTOPPED", "Unblocked and clone removed.")
    cursor.connection.commit()
    return {"message": "Test unstopped successfully."}


def uncomplete_test(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    if test_data := cursor.fetchone():
        verify_lane_access(current_user, str(test_data[0]))
        cursor.execute("UPDATE tests SET stages = 'SCHEDULED' WHERE id = %s", (test_id,))
        log_test_history(cursor, test_id, current_user['id'], "UNCOMPLETED", "Reverted to Scheduled.")
        cursor.connection.commit()
        return {"message": "Test uncompleted."}
    raise HTTPException(status_code=404, detail="Test not found")


def create_assignment(cursor, assign, current_user: dict):
    cursor.execute(
        'SELECT a.id FROM assignments a WHERE a.user_id = %s AND a.week_number = %s AND a.year = %s AND a.test_id = %s',
        (str(assign.user_id), assign.week_number, assign.year, str(assign.test_id)))
    if cursor.fetchone(): raise HTTPException(status_code=400, detail="Already assigned for this week!")

    cursor.execute(
        'INSERT INTO assignments (id, test_id, user_id, week_number, year, allocated_credits) VALUES (%s, %s, %s, %s, %s, %s)',
        (str(uuid.uuid4()), str(assign.test_id), str(assign.user_id), assign.week_number, assign.year,
         assign.allocated_credits))
    cursor.execute("SELECT name FROM tests WHERE id = %s", (str(assign.test_id),))
    test_row = cursor.fetchone()
    if test_row: cursor.execute(
        "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
        (str(uuid.uuid4()), str(assign.user_id), f"Assigned to {test_row[0]} Wk {assign.week_number}.", "ASSIGNMENT"))

    cursor.execute("SELECT name FROM users WHERE id = %s", (str(assign.user_id),))
    log_test_history(cursor, str(assign.test_id), current_user['id'], "ASSIGNED",
                     f"Assigned {(cursor.fetchone() or ['Unknown'])[0]} for Wk {assign.week_number}.")
    cursor.connection.commit()
    return {"message": "Successfully Assigned"}


def remove_assignment(cursor, test_id: str, user_id: str, current_user: dict):
    cursor.execute("SELECT name FROM tests WHERE id = %s", (test_id,))
    if test_row := cursor.fetchone(): cursor.execute(
        "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
        (str(uuid.uuid4()), str(user_id), f"Removed from {test_row[0]}.", "REMOVAL"))
    cursor.execute('DELETE FROM assignments WHERE test_id = %s AND user_id = %s', (test_id, user_id))
    cursor.execute("SELECT name FROM users WHERE id = %s", (user_id,))
    log_test_history(cursor, test_id, current_user['id'], "UNASSIGNED",
                     f"Removed {(cursor.fetchone() or ['Unknown'])[0]}.")
    cursor.connection.commit()
    return {"message": "Successfully Unassigned"}


def get_test_history(cursor, test_id: str, current_user: dict):
    where_clauses, params = ["th.test_id = %s"], [test_id]
    if current_user.get('role') == 'maintainer':
        where_clauses.append("t.service_lane_id = %s")
        params.append(str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))
    cursor.execute(
        f"SELECT th.id, th.action, th.details, th.timestamp, u.name as user_name FROM test_history th LEFT JOIN users u ON th.user_id = u.id WHERE {' AND '.join(where_clauses)} ORDER BY th.timestamp DESC",
        tuple(params))
    return [dict(zip([col[0] for col in cursor.description], row)) for row in cursor.fetchall()]


def get_test_secret(cursor, test_id: str, current_user: dict):
    if current_user.get('role') not in ['admin', 'pentester']: raise HTTPException(status_code=403,
                                                                                   detail="No access to Secure Notes.")
    cursor.execute("SELECT encrypted_data FROM secret_notes WHERE test_id = %s", (test_id,))
    if not (note_row := cursor.fetchone()): return {"exists": False}
    cursor.execute("SELECT encrypted_key FROM secret_note_access WHERE test_id = %s AND user_id = %s",
                   (test_id, str(current_user["id"])))
    key_row = cursor.fetchone()
    cursor.execute("SELECT user_id FROM secret_note_access WHERE test_id = %s", (test_id,))
    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_FETCHED", "TEST_SECRET",
                    details=f"Fetched secret {test_id}.")
    return {"exists": True, "encrypted_data": note_row[0], "encrypted_key": key_row[0] if key_row else None,
            "shared_with": [str(r[0]) for r in cursor.fetchall()]}


def update_test_secret(cursor, test_id: str, payload: dict, current_user: dict):
    if current_user.get('role') not in ['admin', 'pentester']: raise HTTPException(status_code=403, detail="No access.")
    cursor.execute(
        'INSERT INTO secret_notes (test_id, encrypted_data, updated_at) VALUES (%s, %s, CURRENT_TIMESTAMP) ON CONFLICT (test_id) DO UPDATE SET encrypted_data = EXCLUDED.encrypted_data, updated_at = CURRENT_TIMESTAMP',
        (test_id, payload.get("encrypted_data")))
    cursor.execute("DELETE FROM secret_note_access WHERE test_id = %s", (test_id,))
    for access in payload.get("access_list", []): cursor.execute(
        'INSERT INTO secret_note_access (test_id, user_id, encrypted_key) VALUES (%s, %s, %s)',
        (test_id, access["user_id"], access["encrypted_key"]))
    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_UPDATED", "TEST_SECRET",
                    details=f"Updated secret {test_id}.")
    cursor.connection.commit()
    return {"message": "Secure note vaulted."}


def delete_test_secret(cursor, test_id: str, current_user: dict):
    if current_user.get('role') not in ['admin', 'pentester']: raise HTTPException(status_code=403, detail="No access.")
    cursor.execute("DELETE FROM secret_notes WHERE test_id = %s", (test_id,))
    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_DELETED", "TEST_SECRET",
                    details=f"Deleted secret {test_id}.")
    cursor.connection.commit()
    return {"message": "Secure note deleted."}


def get_milestones(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    if row := cursor.fetchone():
        verify_lane_access(current_user, str(row[0]))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")
    cursor.execute("SELECT step_name, is_completed FROM test_milestones WHERE test_id = %s", (test_id,))
    return {r[0]: r[1] for r in cursor.fetchall()}


def update_milestone(cursor, test_id: str, payload, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    if row := cursor.fetchone():
        verify_lane_access(current_user, str(row[0]))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")
    cursor.execute(
        "INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, %s, %s) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = EXCLUDED.is_completed",
        (test_id, payload.step_name, payload.is_completed))
    cursor.connection.commit()
    return {"message": "Updated"}


def get_requirements(cursor, test_id: str, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    if row := cursor.fetchone():
        verify_lane_access(current_user, str(row[0]))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")
    cursor.execute("SELECT id, description, is_completed FROM test_requirements WHERE test_id = %s ORDER BY id",
                   (test_id,))
    return [{"id": str(r[0]), "description": r[1], "is_completed": r[2]} for r in cursor.fetchall()]


def add_requirement(cursor, test_id: str, req, current_user: dict):
    cursor.execute("SELECT service_lane_id FROM tests WHERE id = %s", (test_id,))
    if row := cursor.fetchone():
        verify_lane_access(current_user, str(row[0]))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")
    cursor.execute(
        "INSERT INTO test_requirements (id, test_id, description, is_completed) VALUES (gen_random_uuid(), %s, %s, false) RETURNING id",
        (test_id, req.description))
    req_id = cursor.fetchone()[0]
    cursor.connection.commit()
    return {"id": str(req_id), "description": req.description, "is_completed": False}


def delete_requirement(cursor, req_id: str, current_user: dict):
    cursor.execute(
        "SELECT tr.test_id, t.service_lane_id FROM test_requirements tr JOIN tests t ON tr.test_id = t.id WHERE tr.id = %s",
        (req_id,))
    if not (row := cursor.fetchone()): raise HTTPException(status_code=404, detail="Not found.")
    verify_lane_access(current_user, str(row[1]))
    cursor.execute("DELETE FROM test_requirements WHERE id = %s", (req_id,))
    cursor.connection.commit()
    return {"message": "Deleted"}


def toggle_requirement(cursor, req_id: str, current_user: dict):
    cursor.execute(
        "SELECT t.id, t.service_lane_id FROM test_requirements tr JOIN tests t ON tr.test_id = t.id WHERE tr.id = %s",
        (req_id,))
    if not (row := cursor.fetchone()): raise HTTPException(status_code=404, detail="Not found.")
    test_id, service_lane_id = row
    verify_lane_access(current_user, str(service_lane_id))

    cursor.execute("UPDATE test_requirements SET is_completed = NOT is_completed WHERE id = %s RETURNING is_completed",
                   (req_id,))
    new_status = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*), SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) FROM test_requirements WHERE test_id = %s",
        (test_id,))
    total_reqs, completed_reqs = cursor.fetchone()

    if total_reqs > 0 and total_reqs == completed_reqs:
        cursor.execute(
            "INSERT INTO test_milestones (id, test_id, step_name, is_completed) VALUES (gen_random_uuid(), %s, 'Requirements', true) ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true",
            (test_id,))
    else:
        cursor.execute(
            "UPDATE test_milestones SET is_completed = false WHERE test_id = %s AND step_name = 'Requirements'",
            (test_id,))

    cursor.connection.commit()
    return {"is_completed": new_status, "all_completed": total_reqs == completed_reqs}