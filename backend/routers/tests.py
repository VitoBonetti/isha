from typing import List
import uuid
import os
import json
import asyncio
import requests
import traceback
from datetime import datetime, timedelta, timezone
from pydantic import UUID4
from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks
import google.auth.transport.requests
import google.oauth2.id_token
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin, require_write_access
from websockets_manager import manager
from schema import (
    TestCreate,
    TestBase,
    AssignmentBase,
    TestSchedule,
    BulkTestCreate,
    AssignmentCreate,
    SecureNotePayload,
    TestAnalysisResponse,
    RequirementCreate,
    MilestoneUpdate
)
from audit_logger import log_audit_event
from utils.drive_manager import (
    DriveManager,
    background_archive_workspace,
    background_provision_workspace,
    background_relocate_workspace
)
from utils.secret_manager import get_secret
from utils.vuln_analysis import build_payload, run_cloud_run_analysis
from utils.security_chipher import get_cipher
from presentations.presentation import generate_presentation
from reports import osrgt_v3, pdf_gen


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

KISS24_BASE_URL = str(os.environ.get("KISS_24_ENDPOINT"))
CUTOFF_DATE = datetime(2026, 5, 1, tzinfo=timezone.utc)
BASE_URL = str(os.environ.get("FRONTEND_URL"))


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


# --- HELPER: report generations ---
def fetch_all_kiss24(endpoint: str, api_key: str, payload: dict = None):
    """Helper to fetch all paginated results from KISS24 with safe JSON parsing."""
    if payload is None: payload = {}

    # CRITICAL FIX: Ensure no newlines exist in the API key header
    headers = {'x-api-key': api_key.strip(), 'Content-Type': 'application/json'}
    items = []
    page = 1

    with requests.Session() as session:
        while True:
            url = f"{KISS24_BASE_URL}{endpoint}"
            response = session.post(url, headers=headers, params={'page': page}, json=payload, timeout=30)

            if not response.ok:
                if response.status_code == 400 and "Invalid Page Number" in response.text:
                    break
                else:
                    raise ValueError(f"API Error on {endpoint}. Status: {response.status_code}, Body: {response.text}")

            # CRITICAL FIX: Catch non-JSON HTML pages returned by WAFs
            try:
                data = response.json()
            except Exception:
                raise ValueError(
                    f"Invalid JSON returned from {url}. Status: {response.status_code}. Raw Body: {response.text[:300]}")

            items.extend(data.get('items', []))

            page_count = int(data.get('page_count', 1))
            if page >= page_count: break
            page += 1

    return items


def get_vuln_fields_map(vuln_uuids: list, api_key: str):
    """Fetches custom fields for vulnerabilities in chunks."""
    vuln_fields_map = {}
    if not vuln_uuids: return vuln_fields_map

    chunk_size = 20
    for i in range(0, len(vuln_uuids), chunk_size):
        chunk = vuln_uuids[i:i + chunk_size]
        fields_data = fetch_all_kiss24('fields', api_key, {"vulnerabilities": chunk})

        for item in fields_data:
            v_uuid = item.get('entity', {}).get('uuid')
            if v_uuid:
                if v_uuid not in vuln_fields_map:
                    vuln_fields_map[v_uuid] = []
                vuln_fields_map[v_uuid].append(item)

    return vuln_fields_map


def _is_field_populated(field_obj):
    val = field_obj.get('value')
    if val is None: return False
    if isinstance(val, list): return len(val) > 0
    if isinstance(val, str): return bool(val.strip())
    return True


def validate_kiss24_findings(vulns: list, vuln_fields_map: dict, report_type: int, api_key: str):
    """Validates contexts and MITRE ID fields, returning a list of violations."""
    invalid_findings = []
    context_cache = {}

    for vuln in vulns:
        vuln_uuid = vuln['uuid']
        reasons = []

        if report_type == 1:
            ctx_name = vuln.get('context', {}).get('name', '')
            if not ctx_name:
                vt_uuid = vuln.get('vulnerability_type', {}).get('uuid')
                if vt_uuid:
                    if vt_uuid not in context_cache:
                        ctxs = fetch_all_kiss24('provider/contexts', api_key,
                                                {"vulnerability_types": [vt_uuid]})
                        context_cache[vt_uuid] = ctxs[0].get('name', '') if ctxs else ''
                    ctx_name = context_cache[vt_uuid]

            if not ctx_name.startswith("[Adv Sim]"):
                reasons.append(f"Context '{ctx_name}' does not start with '[Adv Sim]'")

            mitre_filled = False
            for field in vuln_fields_map.get(vuln_uuid, []):
                if field.get('custom_field', {}).get('name') == 'MITRE ID':
                    if _is_field_populated(field): mitre_filled = True
                    break
            if not mitre_filled:
                reasons.append("MITRE ID custom field is empty or missing")

        created_at_str = vuln.get('created_at') or vuln.get('published_at', '')
        try:
            created_date = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
            if created_date.tzinfo is None:
                created_date = created_date.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError):
            created_date = datetime.now(timezone.utc)

        if created_date > CUTOFF_DATE:
            effort_filled = False
            for field in vuln_fields_map.get(vuln_uuid, []):
                if field.get('custom_field', {}).get('name') == 'Remediation Effort':
                    if _is_field_populated(field): effort_filled = True
                    break
            if not effort_filled:
                reasons.append("Remediation Effort custom field is missing (Required for new vulns)")

        if reasons:
            invalid_findings.append({
                "vuln_uuid": vuln_uuid,
                "reasons": reasons
            })

    return invalid_findings


async def process_presentation_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, user_role: str, test_name: str,
                                          drive_folder_id: str, service_name: str, snow_number: str,
                                          start_week: int, start_year: int, duration_weeks: float):
    """Background task that generates the presentation locally via a thread."""
    try:
        # Pass the database values to the generator
        data = await asyncio.to_thread(
            generate_presentation,
            kiss24_id,
            drive_folder_id,
            service_name,
            snow_number,
            start_week,
            start_year,
            duration_weeks
        )

        drive_link = data.get("driveLink", "No link returned")
        file_id = data.get("fileId")
        file_name = data.get("fileName")
        warnings_dict = data.get("warnings", {})

        if file_id and file_name:
            with db_cursor_context() as cursor:
                if cursor:
                    cursor.execute("""
                        INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, last_modified, synced_at)
                        VALUES (gen_random_uuid(), %s, %s, %s, 'application/vnd.openxmlformats-officedocument.presentationml.presentation', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        ON CONFLICT (drive_file_id) DO UPDATE SET 
                            last_modified = CURRENT_TIMESTAMP, 
                            synced_at = CURRENT_TIMESTAMP
                    """, (test_id, file_id, file_name, drive_link))
                    cursor.execute("""
                        INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
                        VALUES (gen_random_uuid(), %s, 'Generate Presentation', true)
                        ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true
                    """, (test_id,))
                    cursor.connection.commit()

        # Format the unhealthy warnings into a readable list
        issues = []
        if isinstance(warnings_dict, dict):
            for key, info in warnings_dict.items():
                if isinstance(info, dict) and not info.get("healthy"):
                    issues.append(f"{key.capitalize()}: {info.get('reason')}")

        if issues:
            issues_text = "\n\n[!] Warnings:\n- " + "\n- ".join(issues)
        else:
            issues_text = "\n\n[+] Health Check: 100% Healthy (No warnings)"

        message = f"Presentation for '{test_name}' is ready!\nLink: {drive_link}{issues_text}"
        notif_type = "SUCCESS"

        await manager.broadcast(json.dumps({
            "action": "PRESENTATION_READY",
            "email": user_email,
            "message": f"Presentation for {test_name} generated successfully!"
        }))

    except Exception as e:
        print(f"Error generating presentation: {e}")
        message = f"Generation failed for '{test_name}'. Error: {str(e)}"
        notif_type = "ERROR"
        await manager.broadcast(json.dumps({
            "action": "PRESENTATION_FAILED",
            "email": user_email,
            "message": message
        }))

    # Save the result as a notification for the user
    with db_cursor_context() as cursor:
        if cursor:
            cursor.execute(
                "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                (str(uuid.uuid4()), user_id, message, notif_type)
            )

    await manager.broadcast('{"action": "REFRESH_BOARD"}')


def get_report_type_id(display_order: int) -> int:
    """Maps the service lane's display_order to the report type expected by osrgt_v3."""
    if display_order == 1:
        return 1  # Adversary Simulation
    elif display_order == 2:
        return 3  # White Box
    else:
        return 2  # Black/Grey Box


async def process_report_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, user_role: str,
                                    test_name: str, drive_folder_id: str, display_order: int,
                                    start_week: int, start_year: int, duration_weeks: float):
    """Background task that generates the HTML & PDF reports, uploads them, and handles logging."""
    try:
        try:
            test_start = datetime.fromisocalendar(start_year, start_week, 1)
            dur_weeks = max(1, int(duration_weeks or 1))
            test_end = test_start + timedelta(days=(dur_weeks - 1) * 7 + 4)
            start_date_str = test_start.strftime("%d-%m-%Y")
            end_date_str = test_end.strftime("%d-%m-%Y")
        except Exception:
            start_date_str = end_date_str = None

        # CRITICAL FIX: Ensure the API key is stripped of whitespace/newlines
        raw_api_key = get_secret(os.environ.get("KISS_24_API_KEY_NAME"))
        api_key = raw_api_key.strip() if raw_api_key else ""

        report_type = get_report_type_id(display_order)

        # 1. RUN VALIDATION BEFORE GENERATING REPORT
        vulns = await asyncio.to_thread(fetch_all_kiss24, 'vulnerabilities', api_key, {"tests": [kiss24_id]})
        vuln_uuids = [v['uuid'] for v in vulns]
        vuln_fields_map = await asyncio.to_thread(get_vuln_fields_map, vuln_uuids, api_key)

        invalid_findings = await asyncio.to_thread(validate_kiss24_findings, vulns, vuln_fields_map, report_type,
                                                   api_key)

        if invalid_findings:
            err_msg = f"Report generation aborted for '{test_name}'. Validation failed:\n"
            for f in invalid_findings:
                err_msg += f"\n- Vuln {f['vuln_uuid']}:\n  " + "\n  ".join(f['reasons'])
            raise ValueError(err_msg)

        # 2. PROCEED WITH GENERATION
        report_args = {
            "pentest": kiss24_id,
            "type": report_type,
            "api_key": api_key,
            "action": "generate",
            "minify": False,
            "environment": "sec24prd",
            "loglevel": "info",
            "devoteam": False,
            "start": start_date_str,
            "end": end_date_str,
            "custom_fields": vuln_fields_map
        }

        html_content, html_filename = await asyncio.to_thread(osrgt_v3.generate_html_report, report_args)
        pdf_content, pdf_filename = await asyncio.to_thread(pdf_gen.convert_html_to_pdf, html_content, html_filename)

        drive_manager = DriveManager()
        html_result = await asyncio.to_thread(drive_manager.upload_file, drive_folder_id, html_filename,
                                              html_content.encode('utf-8'), 'text/html')
        pdf_result = await asyncio.to_thread(drive_manager.upload_file, drive_folder_id, pdf_filename, pdf_content,
                                             'application/pdf')

        with db_cursor_context() as cursor:
            if cursor:
                cursor.execute("""
                    INSERT INTO test_documents (id, test_id, drive_file_id, file_name, mime_type, file_url, last_modified, synced_at)
                    VALUES (gen_random_uuid(), %s, %s, %s, 'application/pdf', %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                    ON CONFLICT (drive_file_id) DO UPDATE SET 
                        last_modified = CURRENT_TIMESTAMP, 
                        synced_at = CURRENT_TIMESTAMP
                """, (test_id, pdf_result["id"], pdf_filename, pdf_result["link"]))
                cursor.execute("""
                    INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
                    VALUES (gen_random_uuid(), %s, 'Generate Report PDF', true)
                    ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true
                """, (test_id,))
                cursor.connection.commit()

        # --- SUCCESS HANDLING ---
        message = f"Report for '{test_name}' is ready!\nPDF Link: {pdf_result['link']}"
        await manager.broadcast(json.dumps({"action": "REPORT_READY", "email": user_email, "message": message}))

        with db_cursor_context() as cursor:
            if cursor:
                cursor.execute(
                    "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (str(uuid.uuid4()), user_id, message, "SUCCESS")
                )
                cursor.connection.commit()

        await asyncio.to_thread(
            log_audit_event,
            user_id=user_id,
            role=user_role,
            action="REPORT_GENERATION_SUCCESS",
            resource_type="REPORTING",
            resource_id=test_id,
            details=f"Successfully generated and uploaded PDF report for '{test_name}'."
        )

    except Exception as e:
        error_details = str(e)

        # Catch the full python stack trace so we can debug exactly which line failed in BigQuery
        full_traceback = traceback.format_exc()
        print(f"Error generating report: {error_details}\n{full_traceback}")

        # Format a clean message for the User
        if isinstance(e, ValueError) and (
                "Validation failed" in error_details or "API Error" in error_details or "Invalid JSON" in error_details):
            user_message = error_details
        else:
            user_message = f"Report generation failed for '{test_name}'. Please contact an administrator or check the logs."

        await manager.broadcast(json.dumps({"action": "REPORT_FAILED", "email": user_email, "message": user_message}))

        with db_cursor_context() as cursor:
            if cursor:
                cursor.execute(
                    "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (str(uuid.uuid4()), user_id, user_message, "ERROR")
                )

        # Log the raw technical crash to BigQuery
        await asyncio.to_thread(
            log_audit_event,
            user_id=user_id,
            role=user_role,
            action="REPORT_GENERATION_CRASH",
            resource_type="REPORTING",
            resource_id=test_id,
            details=f"Crash during report generation for '{test_name}': {error_details}\nTraceback: {full_traceback}"
        )

    await manager.broadcast('{"action": "REFRESH_BOARD"}')


# --- HELPER: Vulnerability analysis ---
async def process_vuln_analysis_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, test_name: str):
    try:
        # 1. Build Payload
        payload = await build_payload(kiss24_id)
        if not payload or not payload.get("vulnerabilities"):
            raise ValueError("No vulnerabilities found to analyze.")

        # 2. Call Cloud Run
        analysis_response = await run_cloud_run_analysis(payload)

        # 3. Stitch Markdown
        results = analysis_response.get("results", [])
        stitched_markdown = "\n\n---\n\n".join([r.get("analysis", "") for r in results if r.get("status") == "success"])

        if not stitched_markdown:
            raise ValueError("Cloud Run returned no valid analysis text.")

        # 4. Save to Database
        with db_cursor_context() as cursor:
            if cursor:
                cursor.execute("""
                    UPDATE test_analyses 
                    SET status = 'COMPLETED', analysis_text = %s, timestamp = CURRENT_TIMESTAMP 
                    WHERE test_id = %s
                """, (stitched_markdown, test_id))

                cursor.execute("""
                    INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
                    VALUES (gen_random_uuid(), %s, 'Validate Finding', true)
                    ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true
                """, (test_id,))
                cursor.connection.commit()

        # 5. Notify User
        db_message = f"Vulnerability Analysis for '{test_name}' is ready! Link: {BASE_URL}/tests/{test_id}/analysis"
        with db_cursor_context() as cursor:
            if cursor:
                cursor.execute(
                    "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (str(uuid.uuid4()), user_id, db_message, "SUCCESS")
                )
                cursor.connection.commit()

        toast_message = f"Vulnerability Analysis for '{test_name}' is ready!"
        await manager.broadcast(json.dumps({
            "action": "REPORT_READY",
            "email": user_email,
            "message": toast_message,
            "link": f"/tests/{test_id}/analysis"
        }))

    except Exception as e:
        print(f"Analysis failed: {e}")
        with db_cursor_context() as cursor:
            if cursor:
                cursor.execute(
                    "UPDATE test_analyses SET status = 'FAILED', timestamp = CURRENT_TIMESTAMP WHERE test_id = %s",
                    (test_id,))
                cursor.connection.commit()

        await manager.broadcast(json.dumps({
            "action": "REPORT_FAILED",
            "email": user_email,
            "message": f"Analysis failed for '{test_name}': {str(e)}"
        }))


# --- HELPER: bulk generation ---
def process_bulk_tests_background(asset_ids: List[UUID4], user_id: str, role: str,):
    tests_to_provision = []

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

            log_audit_event(
                user_id=str(user_id),
                role=str(role),
                action="TEST_CREATED",
                resource_type="TESTS",
                resource_id=str(new_test_id),
                details=f"Test {asset_name} with ID: {new_test_id} was created. Service Lane ID: {service_lane_id} in a Bulk Action."
            )

            cursor.execute('INSERT INTO test_assets (test_id, asset_id) VALUES (%s, %s)', (new_test_id, str(asset_id)))
            log_test_history(cursor, new_test_id, user_id, "GENERATED", f"Test generated from Asset Pool.")

            # Store the data to provision later
            current_year = datetime.now().year
            tests_to_provision.append(
                (new_test_id, current_year, service_name, country_name, asset_name, auto_provision))

        # Commit the transaction so the database unlocks the rows!
        cursor.connection.commit()

    # Now that the DB is unlocked, we can safely contact Google Drive
    for test_id, year, s_name, c_name, t_name, auto_prov in tests_to_provision:
        if auto_prov:
            DriveManager().provision_test_workspace(test_id, year, s_name, c_name, t_name)


# --- Test endpoint api ---
@router.post("/", summary="[Admin Only] Create a new Test")
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

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="TEST_CREATED",
        resource_type="TESTS",
        resource_id=str(new_test_id),
        details=f"Test {t.name} with ID: {new_test_id} was created. Service Lane ID: {t.service_lane_id}."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test created successfully", "id": new_id}


@router.get("/", summary="Return all tests")
def get_all_tests(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute('''
        SELECT t.id, t.name, t.start_week, t.start_year, t.duration_weeks, t.stages::text as status,
            s.name as service_lane_name, s.is_active as is_service_active,
            s.auto_provision_workspace,
            COALESCE((SELECT string_agg(DISTINCT u.name, ', ') FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = t.id), 'Unassigned') as assigned_pentesters,
            EXISTS(SELECT 1 FROM secret_notes WHERE test_id = t.id) as has_secret,
            t.drive_folder_url,
            t.kiss24,
            (SELECT a.raw_asset_id FROM test_assets ta JOIN assets a ON ta.asset_id = a.id WHERE ta.test_id = t.id LIMIT 1) as raw_asset_id
        FROM tests t LEFT JOIN services_lanes s ON t.service_lane_id = s.id
        ORDER BY t.start_year DESC NULLS LAST, t.start_week DESC NULLS LAST, t.name ASC
    ''')
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.get("/{test_id}", summary="Get Full Test Details & Contacts")
def get_test_details(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # 1. Fetch Test Base Details
    cursor.execute('''
                SELECT t.id, t.name, t.service_lane_id, t.credits_per_week, 
                       t.duration_weeks, t.stages::text as status, t.start_week, t.start_year, 
                       t.is_tentative, t.kiss24, t.drive_folder_id, t.drive_folder_url,
                       s.name as service_lane_name, s.auto_provision_workspace,
                       ct.kiss24_uuid as country_kiss24_uuid,
                       EXISTS(SELECT 1 FROM secret_notes WHERE test_id = t.id) as has_secret,
                       COALESCE((SELECT string_agg(DISTINCT u.name, ', ') FROM assignments a JOIN users u ON a.user_id = u.id WHERE a.test_id = t.id), 'Unassigned') as assigned_pentesters,
                       ra.category_id,
                       c.name as category_name
                FROM tests t
                LEFT JOIN services_lanes s ON t.service_lane_id = s.id
                LEFT JOIN test_assets ta ON t.id = ta.test_id
                LEFT JOIN assets a ON ta.asset_id = a.id
                LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
                LEFT JOIN service_categories c ON ra.category_id = c.id
                LEFT JOIN countries ct ON ra.country_id = ct.id
                WHERE t.id = %s
                LIMIT 1
            ''', (test_id,))
    test_row = cursor.fetchone()
    if not test_row: raise HTTPException(status_code=404, detail="Test not found")

    columns = [desc[0] for desc in cursor.description]
    test_data = dict(zip(columns, test_row))

    # 2. Fetch Attached Assets
    cursor.execute('''
            SELECT a.id as asset_id, a.raw_asset_id, r.name as asset_name, r.country_id, r.kiss24_asset_id
            FROM test_assets ta
            JOIN assets a ON ta.asset_id = a.id
            JOIN raw_assets r ON a.raw_asset_id = r.id
            WHERE ta.test_id = %s
        ''', (test_id,))
    assets_cols = [desc[0] for desc in cursor.description]
    assets_data = [dict(zip(assets_cols, row)) for row in cursor.fetchall()]
    test_data["assets"] = assets_data

    # Extract IDs for contacts aggregation
    raw_asset_ids = [a['raw_asset_id'] for a in assets_data if a['raw_asset_id']]
    country_ids = list(set([a['country_id'] for a in assets_data if a['country_id']]))

    # 3. Fetch Asset Contacts (Combined across all linked assets)
    asset_contacts = []
    if raw_asset_ids:
        format_strings = ','.join(['%s'] * len(raw_asset_ids))
        cursor.execute(f'''
            SELECT DISTINCT c.id as contact_id, c.email, c.full_name, 
                   rac.is_stakeholder, rac.is_developer
            FROM raw_asset_contacts rac
            JOIN contacts c ON rac.contact_id = c.id
            WHERE rac.raw_asset_id IN ({format_strings})
            ORDER BY c.email ASC
        ''', tuple(raw_asset_ids))
        ac_cols = [desc[0] for desc in cursor.description]
        asset_contacts = [dict(zip(ac_cols, row)) for row in cursor.fetchall()]
    test_data["asset_contacts"] = asset_contacts

    # 4. Fetch Country Contacts (Combined across all linked asset regions)
    country_contacts = []
    if country_ids:
        format_strings = ','.join(['%s'] * len(country_ids))
        cursor.execute(f'''
            SELECT DISTINCT c.id as contact_id, c.email, c.full_name, 
                   cc.is_stakeholder, cc.is_developer
            FROM country_contacts cc
            JOIN contacts c ON cc.contact_id = c.id
            WHERE cc.country_id IN ({format_strings})
            ORDER BY c.email ASC
        ''', tuple(country_ids))
        cc_cols = [desc[0] for desc in cursor.description]
        country_contacts = [dict(zip(cc_cols, row)) for row in cursor.fetchall()]
    test_data["country_contacts"] = country_contacts

    # 5. Fetch Test History
    cursor.execute('''
        SELECT th.id, th.action, th.details, th.timestamp, u.name as user_name
        FROM test_history th
        LEFT JOIN users u ON th.user_id = u.id
        WHERE th.test_id = %s
        ORDER BY th.timestamp DESC
    ''', (test_id,))
    hist_cols = [desc[0] for desc in cursor.description]
    test_data["history"] = [dict(zip(hist_cols, row)) for row in cursor.fetchall()]

    return test_data


@router.put("/{test_id}", summary="[Admin Only] Update a specific test")
def update_test(test_id: str, t: TestBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # 1. Fetch old data to see if we need to relocate the Google Drive folder
    cursor.execute('''
        SELECT t.drive_folder_id, s.name, c.name, t.start_year
        FROM tests t
        LEFT JOIN services_lanes s ON t.service_lane_id = s.id
        LEFT JOIN test_assets ta ON t.id = ta.test_id
        LEFT JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN countries c ON a.country_id = c.id
        WHERE t.id = %s LIMIT 1
    ''', (test_id,))
    old_data = cursor.fetchone()

    db_stage = FRONTEND_TO_DB_STAGES.get(t.status, "NOT_PLANNED")
    if db_stage == 'NOT_PLANNED':
        cursor.execute('DELETE FROM assignments WHERE test_id = %s', (test_id,))
        cursor.execute('UPDATE tests SET start_week = NULL, start_year = NULL WHERE id = %s', (test_id,))

    cat_id = str(t.category_id) if hasattr(t, 'category_id') and t.category_id else None
    kiss24_val = str(t.kiss24) if hasattr(t, 'kiss24') and t.kiss24 else None

    # Update the test
    cursor.execute('''
        UPDATE tests 
         SET name=%s, service_lane_id=%s, category_id=%s, credits_per_week=%s, duration_weeks=%s, stages=%s, is_tentative=%s, kiss24=%s
        WHERE id=%s
    ''', (t.name, str(t.service_lane_id), cat_id, t.credits_per_week, t.duration_weeks, db_stage,
          t.is_tentative, kiss24_val,
          test_id))

    cursor.execute('''
        UPDATE raw_assets 
        SET category_id = %s 
        WHERE id IN (
            SELECT a.raw_asset_id 
            FROM test_assets ta 
            JOIN assets a ON ta.asset_id = a.id 
            WHERE ta.test_id = %s
        )
    ''', (cat_id, test_id))

    log_test_history(cursor, test_id, current_user['id'], "UPDATED",
                     f"Settings updated: {t.credits_per_week}cr, {t.duration_weeks}wks.")
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="TEST_UPDATED",
        resource_type="TESTS",
        resource_id=str(test_id),
        details=f"Test with ID: {test_id} was updated."
    )

    # 2. Trigger Folder Relocation if a folder exists
    if old_data and old_data[0]:
        folder_id = old_data[0]
        country_name = old_data[2] or "General"

        # Ensure we pass the NEW year if it was updated, otherwise fallback to the old year
        target_year = t.start_year if t.start_year else (old_data[3] or datetime.now().year)

        # Get the new service name to construct the new path
        cursor.execute("SELECT name FROM services_lanes WHERE id = %s", (str(t.service_lane_id),))
        new_service_name = cursor.fetchone()[0]

        background_tasks.add_task(background_relocate_workspace, folder_id, target_year, new_service_name, country_name, t.name)

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test updated successfully."}


@router.delete("/{test_id}", summary="[Admin Only] Delete a specific test")
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

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="TEST_DELETED",
        resource_type="TESTS",
        resource_id=str(test_id),
        details=f"Test with ID: {test_id} was deleted."
    )

    if test_data and test_data[1]:
        test_name, folder_id = test_data[0], test_data[1]
        background_tasks.add_task(background_archive_workspace, folder_id, test_name)

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test permanently deleted and assets freed."}


@router.post("/bulk", summary="[Admin Only] bulk creation of tests")
def bulk_create_tests(req: BulkTestCreate, background_tasks: BackgroundTasks,
                      current_user: dict = Depends(require_admin)):
    background_tasks.add_task(process_bulk_tests_background, req.asset_ids, str(current_user['id']), str(current_user['role']))
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Generating {len(req.asset_ids)} tests from active pool."}


@router.post("/{test_id}/workspace", summary="[Admin Only] Create workspace on Google for each test")
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


@router.put("/{test_id}/tentative", summary="[Admin Only] Flag the test as Tentative")
def toggle_tentative(test_id: str, background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Flips the boolean from True to False, or False to True
    cursor.execute("UPDATE tests SET is_tentative = NOT is_tentative WHERE id = %s", (test_id,))

    # Log it
    cursor.execute("SELECT is_tentative FROM tests WHERE id = %s", (test_id,))
    is_tent = cursor.fetchone()[0]
    state_str = "Marked as Tentative (TBC)" if is_tent else "Removed Tentative mark"
    log_test_history(cursor, test_id, current_user['id'], "UPDATED", state_str)

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": state_str}


# --- test Scheduling ---
@router.put("/{test_id}/schedule", summary="[Admin Only] Schedule a test")
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

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="TEST_SCHEDULED",
        resource_type="TESTS",
        resource_id=str(test_id),
        details=f"Test with ID: {test_id} was scheduled for Week {schedule.start_week}, {schedule.start_year}."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test scheduled on the board."}


@router.put("/{test_id}/unschedule", summary="[Admin Only] Unschedule a test")
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

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="TEST_UNSCHEDULED",
        resource_type="TESTS",
        resource_id=str(test_id),
        details=f"Test with ID: {test_id} was unscheduled."
    )

    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test returned to backlog."}


@router.put("/{test_id}/complete", summary="[Admin Only] Flag a test as complete")
def complete_test(test_id: str, background_tasks: BackgroundTasks,
                  current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE tests SET stages = 'COMPLETED' WHERE id = %s", (test_id,))

    log_test_history(cursor, test_id, current_user['id'], "COMPLETED", "Test successfully marked as completed.")

    cursor.connection.commit()

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return {"message": "Test marked as Completed."}


@router.put("/{test_id}/unable", summary="[Admin Only] Flag a test as unable")
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


@router.put("/{test_id}/unstop", summary="[Admin Only] Roll back a unable test to normal")
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


@router.put("/{test_id}/uncomplete", summary="[Admin Only] Make un-completing a test cleaner on the backend")
def uncomplete_test(test_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE tests SET stages = 'SCHEDULED' WHERE id = %s", (test_id,))
    log_test_history(cursor, test_id, current_user['id'], "UNCOMPLETED", "Test reverted to Scheduled.")
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Test uncompleted."}


# ---  Assign a test ---
@router.post("/assignments", summary="[Admin Only] Assigne a test to a pentester")
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


@router.delete("/assignments/{test_id}/{user_id}", summary="[Admin Only] Remove pentester from assigned test")
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


# ---  History Test ---
@router.get("/{test_id}/history", summary="REturn the test history")
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


# --- Secure note ---
@router.get("/{test_id}/secret", summary="Return the test secret")
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


@router.put("/{test_id}/secret", summary="Update the test secret")
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


@router.delete("/{test_id}/secret", summary="[Admin Only] Delete the test secret")
def delete_test_secret(test_id: str, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM secret_notes WHERE test_id = %s", (test_id,))
    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_DELETED", "TEST_SECRET", details=f"Deleted secure note for test {test_id}.")
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Secure note permanently deleted."}

# --- Generation PPT ---
@router.post("/{test_id}/presentation", summary="Create a new presentation")
def trigger_presentation_generation(test_id: str, background_tasks: BackgroundTasks,
                                    current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=403, detail="Read-only users cannot trigger generation.")

    cursor.execute("""
        SELECT t.name, t.kiss24, t.drive_folder_id, sl.name as service_name, ra.snow_number,
               t.start_week, t.start_year, t.duration_weeks
        FROM tests t
        LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
        LEFT JOIN test_assets ta ON t.id = ta.test_id
        LEFT JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
        WHERE t.id = %s LIMIT 1
    """, (test_id,))

    row = cursor.fetchone()

    if not row:
        log_audit_event(
            user_id=str(current_user["id"]),
            role=str(current_user["role"]),
            action="GENERATION_PRESENTATION_TEST_NOT_FOUND",
            resource_type="PRESENTATION",
            resource_id=str(test_id),
            details=f"Test with ID {test_id} was not found."
        )
        raise HTTPException(status_code=404, detail="Test not found.")

    test_name, kiss24_id, drive_folder_id, service_name, snow_number, start_week, start_year, duration_weeks = row

    if not kiss24_id:
        log_audit_event(
            user_id=str(current_user["id"]),
            role=str(current_user["role"]),
            action="GENERATION_PRESENTATION_TEST_NO_KISS UUID",
            resource_type="PRESENTATION",
            resource_id=str(test_id),
            details=f"Test with ID {test_id} is Missing kiss24 UUID."
        )
        raise HTTPException(status_code=400, detail="Missing kiss24 UUID. Please set it in the test settings first.")

    if not drive_folder_id:
        log_audit_event(
            user_id=str(current_user["id"]),
            role=str(current_user["role"]),
            action="GENERATION_PRESENTATION_TEST_NO_DRIVE_WORKSPACE",
            resource_type="PRESENTATION",
            resource_id=str(test_id),
            details=f"Test with ID {test_id} is missing Google Drive Workspace."
        )
        raise HTTPException(status_code=400,
                            detail="Missing Drive Workspace. Please click the 'Create Drive Workspace' button first.")

    background_tasks.add_task(
        process_presentation_background,
        test_id, str(kiss24_id), str(current_user["id"]), current_user["email"], str(current_user["role"]), test_name,
        drive_folder_id, service_name, snow_number, start_week, start_year, duration_weeks
    )

    log_audit_event(
        user_id=str(current_user["id"]),
        role=str(current_user["role"]),
        action="PRESENTATION_TRIGGERED",
        resource_type="PRESENTATION",
        resource_id=str(test_id),
        details=f"Presentation for Kiss24 test with ID: {kiss24_id} was started. Service Lane: {service_name}. SNow Asset ID {snow_number}. Start week: {start_week}. Start year: {start_year}"
    )

    return {
        "message": "Presentation generation started in the background. You will receive a notification when it's ready!"}


# --- Generation PDF ---
@router.post("/{test_id}/report", summary="Generate PDF report")
def trigger_report_generation(test_id: str, background_tasks: BackgroundTasks,
                              current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """API Endpoint to trigger the background report generation."""

    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=403, detail="Read-only users cannot trigger generation.")

    cursor.execute("""
        SELECT t.name, t.kiss24, t.drive_folder_id, sl.display_order,
               t.start_week, t.start_year, t.duration_weeks
        FROM tests t
        LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
        WHERE t.id = %s LIMIT 1
    """, (test_id,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Test not found.")

    test_name, kiss24_id, drive_folder_id, display_order, start_week, start_year, duration_weeks = row

    if not kiss24_id:
        raise HTTPException(status_code=400, detail="Missing kiss24 UUID. Please set it in the test settings first.")

    if not drive_folder_id:
        raise HTTPException(status_code=400, detail="Missing Drive Workspace. Please provision the workspace first.")

    safe_display_order = display_order if display_order is not None else 99

    # Notice the injection of `str(current_user["role"])` here
    background_tasks.add_task(
        process_report_background,
        test_id, str(kiss24_id), str(current_user["id"]), current_user["email"], str(current_user["role"]),
        test_name, drive_folder_id, safe_display_order, start_week, start_year, duration_weeks
    )

    log_audit_event(
        user_id=str(current_user["id"]),
        role=str(current_user["role"]),
        action="REPORT_TRIGGERED",
        resource_type="REPORTING",
        resource_id=str(test_id),
        details=f"Report generation triggered for test {test_name} (Kiss24: {kiss24_id})."
    )

    return {
        "message": "Report generation started in the background. You will receive a notification when it's ready!"
    }


# --- Vulne analysis ---
@router.get("/{test_id}/analysis", response_model=TestAnalysisResponse, summary="Get Analysis report")
def get_test_analysis(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """Check if an analysis exists and retrieve it."""
    cursor.execute("SELECT status, analysis_text, timestamp FROM test_analyses WHERE test_id = %s", (test_id,))
    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="No analysis found.")

    return {
        "status": row[0],
        "analysis_text": row[1],
        "timestamp": row[2]
    }


@router.post("/{test_id}/analysis", summary="Perform vulnerabilities analysis")
def trigger_test_analysis(test_id: str, background_tasks: BackgroundTasks,
                          current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """Creates a PENDING record and triggers the background generator."""
    if current_user.get('role') == 'read_only':
        raise HTTPException(status_code=403, detail="Read-only users cannot trigger generation.")

    # Get Test Data
    cursor.execute("SELECT name, kiss24 FROM tests WHERE id = %s", (test_id,))
    row = cursor.fetchone()
    if not row or not row[1]:
        raise HTTPException(status_code=400, detail="Missing Kiss24 UUID.")

    test_name, kiss24_id = row[0], row[1]

    # Upsert PENDING status
    cursor.execute("""
        INSERT INTO test_analyses (test_id, status, timestamp) 
        VALUES (%s, 'PENDING', CURRENT_TIMESTAMP)
        ON CONFLICT (test_id) DO UPDATE SET status = 'PENDING', analysis_text = NULL, timestamp = CURRENT_TIMESTAMP
    """, (test_id,))
    cursor.connection.commit()

    # Trigger Background Task
    background_tasks.add_task(
        process_vuln_analysis_background,
        test_id, str(kiss24_id), str(current_user["id"]), current_user["email"], test_name
    )

    return {"message": "Analysis started in the background."}


# -- Milestones ---
@router.get("/{test_id}/milestones", summary="Get Milestones test")
def get_milestones(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT step_name, is_completed FROM test_milestones WHERE test_id = %s", (test_id,))
    # Return a simple dictionary: {"Information Email Sent": true, "Intake Meeting Planned": false}
    return {row[0]: row[1] for row in cursor.fetchall()}


@router.put("/{test_id}/milestones", summary="Update Milestones test")
def update_milestone(test_id: str, payload: MilestoneUpdate, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # UPSERT logic: Insert it, or if it exists, update the boolean
    cursor.execute("""
        INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
        VALUES (gen_random_uuid(), %s, %s, %s)
        ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = EXCLUDED.is_completed
    """, (test_id, payload.step_name, payload.is_completed))
    cursor.connection.commit()
    return {"message": "Updated"}


@router.get("/{test_id}/requirements", summary="Get Requirement test")
def get_requirements(test_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT id, description, is_completed FROM test_requirements WHERE test_id = %s ORDER BY id", (test_id,))
    return [{"id": str(r[0]), "description": r[1], "is_completed": r[2]} for r in cursor.fetchall()]


@router.post("/{test_id}/requirements", summary="Add Requirement test")
def add_requirement(test_id: str, req: RequirementCreate, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("""
        INSERT INTO test_requirements (id, test_id, description, is_completed) 
        VALUES (gen_random_uuid(), %s, %s, false) RETURNING id
    """, (test_id, req.description))
    req_id = cursor.fetchone()[0]
    cursor.connection.commit()
    return {"id": str(req_id), "description": req.description, "is_completed": False}


@router.put("/requirements/{req_id}/toggle", summary="Edit Requirement test")
def toggle_requirement(req_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # 1. Toggle the requirement and fetch the parent test_id
    cursor.execute("""
        UPDATE test_requirements SET is_completed = NOT is_completed 
        WHERE id = %s RETURNING is_completed, test_id
    """, (req_id,))

    row = cursor.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Requirement not found.")

    new_status, test_id = row

    # 2. Check if ALL requirements for this test are now complete
    cursor.execute("""
        SELECT 
            COUNT(*) as total_reqs,
            SUM(CASE WHEN is_completed THEN 1 ELSE 0 END) as completed_reqs
        FROM test_requirements
        WHERE test_id = %s
    """, (test_id,))

    total_reqs, completed_reqs = cursor.fetchone()

    # 3. If all are complete, auto-complete the milestone
    if total_reqs > 0 and total_reqs == completed_reqs:
        cursor.execute("""
                INSERT INTO test_milestones (id, test_id, step_name, is_completed) 
                VALUES (gen_random_uuid(), %s, 'Requirements', true)
                ON CONFLICT (test_id, step_name) DO UPDATE SET is_completed = true
            """, (test_id,))
    else:
        # If they uncheck a requirement, uncheck the milestone
        cursor.execute("""
                UPDATE test_milestones 
                SET is_completed = false 
                WHERE test_id = %s AND step_name = 'Requirements'
            """, (test_id,))

    cursor.connection.commit()
    return {"is_completed": new_status, "all_completed": total_reqs == completed_reqs}


@router.delete("/requirements/{req_id}", summary="Delete Requirement test")
def delete_requirement(req_id: str, current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM test_requirements WHERE id = %s", (req_id,))
    cursor.connection.commit()
    return {"message": "Deleted"}
