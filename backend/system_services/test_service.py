import uuid
import os
import json
import asyncio
import traceback
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, and_, text
from sqlalchemy.dialects.postgresql import insert
from models.tests import (
    Tests,
    TestStages,
    TestAssets,
    TestDocuments,
    TestMilestone,
    TestRequirement,
    Assignments,
    TestAnalysis
)
from models.secret_notes import SecretNotes, SecretNoteAccess
from models.histories import TestHistory, AssetHistory
from models.assets import Assets
from models.raw_assets import RawAssets, AssetTypes
from models.territories import Country
from models.services import ServiceLanes, ServiceCategories
from models.users import Users
from models.contacts import Contacts, CountryContacts, RawAssetContacts
from models.notifications import Notifications
from database import SessionLocal
from routers.auth import verify_lane_access
from websockets_manager import manager
from audit_logger import log_audit_event
from utils.drive_manager import (
    DriveManager,
    background_archive_workspace,
    background_provision_workspace,
    background_relocate_workspace
)
from utils.secret_manager import get_secret
from utils.vuln_analysis import build_payload, run_cloud_run_analysis
from system_services.rag_service import process_test_documents_background
from presentations.presentation import generate_presentation
from reports import osrgt_v3, pdf_gen
from utils.kiss24_service import validate_kiss24_findings, get_vuln_fields_map, fetch_all_kiss24, get_report_type_id
from utils.timeaware import aware_utcnow

FRONTEND_TO_DB_STAGES = {
    "Not Planned": TestStages.NOT_PLANNED, "Scheduled": TestStages.SCHEDULED, "In Progress": TestStages.IN_PROGRESS,
    "Stopped": TestStages.STOPPED, "Deleted": TestStages.DELETED, "Completed": TestStages.COMPLETED,
    "Archived": TestStages.ARCHIVED
}
BASE_URL = str(os.environ.get("FRONTEND_URL"))


def log_test_history(db: Session, test_id: str, user_id: str, action: str, details: str = None):
    new_hist = TestHistory(
        id=str(uuid.uuid4()), test_id=test_id, user_id=str(user_id) if user_id else None,
        action=action, details=details, timestamp=aware_utcnow()
    )
    db.add(new_hist)

    # Get associated raw assets and test name
    assets_info = (db.query(Assets.raw_asset_id, Tests.name)
                   .join(TestAssets, Assets.id == TestAssets.asset_id)
                   .join(Tests, TestAssets.test_id == Tests.id)
                   .filter(TestAssets.test_id == test_id).all())

    for raw_asset_id, test_name in assets_info:
        asset_hist = AssetHistory(
            id=str(uuid.uuid4()), raw_asset_id=str(raw_asset_id), user_id=str(user_id) if user_id else None,
            action=action,
            details=f"[Test: {test_name}] {details}" if details else f"[Test: {test_name}] Status updated to {action}.",
            timestamp=aware_utcnow()
        )
        db.add(asset_hist)


# --- BACKGROUND TASKS ---
async def process_presentation_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, user_role: str,
                                          test_name: str, drive_folder_id: str, service_name: str, snow_number: str,
                                          start_week: int, start_year: int, duration_weeks: float):
    try:
        data = await asyncio.to_thread(generate_presentation, kiss24_id, drive_folder_id, service_name, snow_number,
                                       start_week, start_year, duration_weeks)
        if data.get("fileId") and data.get("fileName"):
            db = SessionLocal()
            try:
                # Upsert Document
                stmt_doc = insert(TestDocuments).values(
                    id=str(uuid.uuid4()), test_id=test_id, drive_file_id=data.get("fileId"),
                    file_name=data.get("fileName"),
                    mime_type='application/vnd.openxmlformats-officedocument.presentationml.presentation',
                    file_url=data.get("driveLink", ""), doc_type='PRESENTATION', last_modified=aware_utcnow(),
                    synced_at=aware_utcnow()
                ).on_conflict_do_update(
                    index_elements=['drive_file_id'],
                    set_={'last_modified': aware_utcnow(), 'synced_at': aware_utcnow()}
                )
                db.execute(stmt_doc)

                # Upsert Milestone
                stmt_mile = insert(TestMilestone).values(
                    id=str(uuid.uuid4()), test_id=test_id, step_name='Generate Presentation', is_completed=True
                ).on_conflict_do_update(
                    index_elements=['test_id', 'step_name'], set_={'is_completed': True}
                )
                db.execute(stmt_mile)
                db.commit()
            finally:
                db.close()

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

    db = SessionLocal()
    try:
        db.add(Notifications(id=str(uuid.uuid4()), user_id=user_id, message=message, type=notif_type,
                             created_at=aware_utcnow()))
        db.commit()
    finally:
        db.close()
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

        db = SessionLocal()
        try:
            stmt_doc = insert(TestDocuments).values(
                id=str(uuid.uuid4()), test_id=test_id, drive_file_id=pdf_result["id"], file_name=pdf_filename,
                mime_type='application/pdf', file_url=pdf_result["link"], doc_type='FULL_TEST_REPORT',
                last_modified=aware_utcnow(), synced_at=aware_utcnow()
            ).on_conflict_do_update(
                index_elements=['drive_file_id'], set_={'last_modified': aware_utcnow(), 'synced_at': aware_utcnow()}
            )
            db.execute(stmt_doc)

            stmt_mile = insert(TestMilestone).values(
                id=str(uuid.uuid4()), test_id=test_id, step_name='Generate Report PDF', is_completed=True
            ).on_conflict_do_update(
                index_elements=['test_id', 'step_name'], set_={'is_completed': True}
            )
            db.execute(stmt_mile)
            db.commit()
        finally:
            db.close()

        try:
            await asyncio.to_thread(process_test_documents_background, test_id, user_id, user_role)
        except Exception:
            pass

        message = f"Report for '{test_name}' is ready!\nPDF Link: {pdf_result['link']}"
        await manager.broadcast(json.dumps({"action": "REPORT_READY", "email": user_email, "message": message}))

        db = SessionLocal()
        try:
            db.add(Notifications(id=str(uuid.uuid4()), user_id=user_id, message=message, type="SUCCESS",
                                 created_at=aware_utcnow()))
            db.commit()
        finally:
            db.close()

        await asyncio.to_thread(log_audit_event, user_id=user_id, role=user_role, action="REPORT_GENERATION_SUCCESS",
                                resource_type="REPORTING", resource_id=test_id,
                                details=f"Generated PDF for '{test_name}'.")

    except Exception as e:
        error_details = str(e)
        user_message = error_details if isinstance(e, ValueError) and (
                    "Validation failed" in error_details or "API Error" in error_details) else f"Report generation failed for '{test_name}'."
        await manager.broadcast(json.dumps({"action": "REPORT_FAILED", "email": user_email, "message": user_message}))

        db = SessionLocal()
        try:
            db.add(Notifications(id=str(uuid.uuid4()), user_id=user_id, message=user_message, type="ERROR",
                                 created_at=aware_utcnow()))
            db.commit()
        finally:
            db.close()

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

        db = SessionLocal()
        try:
            for html_content, html_filename in reports_data:
                pdf_content, pdf_filename = await asyncio.to_thread(pdf_gen.convert_html_to_pdf, html_content,
                                                                    html_filename)
                pdf_result = await asyncio.to_thread(drive_manager.upload_file, drive_folder_id, pdf_filename,
                                                     pdf_content, 'application/pdf')

                stmt = insert(TestDocuments).values(
                    id=str(uuid.uuid4()), test_id=test_id, drive_file_id=pdf_result["id"], file_name=pdf_filename,
                    mime_type='application/pdf', file_url=pdf_result["link"], doc_type='VULN_REPORT',
                    last_modified=aware_utcnow(), synced_at=aware_utcnow()
                ).on_conflict_do_update(
                    index_elements=['drive_file_id'],
                    set_={'last_modified': aware_utcnow(), 'synced_at': aware_utcnow()}
                )
                db.execute(stmt)
                uploaded_count += 1
                generated_links.append((pdf_filename, pdf_result["link"]))
            db.commit()
        finally:
            db.close()

        try:
            await asyncio.to_thread(process_test_documents_background, test_id, user_id, user_role)
        except Exception:
            pass

        message = f"Successfully generated {uploaded_count} vuln report(s) for '{test_name}':\n" + "".join(
            [f"• {n}\n  Link: {l}\n" for n, l in generated_links])

        db = SessionLocal()
        try:
            db.add(Notifications(id=str(uuid.uuid4()), user_id=user_id, message=message, type="SUCCESS",
                                 created_at=aware_utcnow()))
            db.commit()
        finally:
            db.close()

        await asyncio.to_thread(log_audit_event, user_id=user_id, role=user_role,
                                action="VULN_REPORT_GENERATION_SUCCESS", resource_type="REPORTING", resource_id=test_id,
                                details=f"Generated {uploaded_count} individual vuln reports.")
        await manager.broadcast(json.dumps({"action": "REPORT_READY", "email": user_email, "message": message}))
    except Exception as e:
        user_message = f"Vuln Report generation failed for '{test_name}': {str(e)}"
        db = SessionLocal()
        try:
            db.add(Notifications(id=str(uuid.uuid4()), user_id=user_id, message=user_message, type="ERROR",
                                 created_at=aware_utcnow()))
            db.commit()
        finally:
            db.close()

        await asyncio.to_thread(log_audit_event, user_id=user_id, role=user_role, action="VULN_REPORT_GENERATION_CRASH",
                                resource_type="REPORTING", resource_id=test_id, details=str(e))
        await manager.broadcast(json.dumps({"action": "REPORT_FAILED", "email": user_email, "message": user_message}))
    await manager.broadcast('{"action": "REFRESH_BOARD"}')


async def process_vuln_analysis_background(test_id: str, kiss24_id: str, user_id: str, user_email: str, test_name: str):
    try:
        payload = await build_payload(kiss24_id)
        if not payload or not payload.get("vulnerabilities"):
            raise ValueError("No vulnerabilities found.")

        analysis_response = await run_cloud_run_analysis(payload)
        stitched_markdown = "\n\n---\n\n".join(
            [r.get("analysis", "") for r in analysis_response.get("results", []) if r.get("status") == "success"])
        if not stitched_markdown:
            raise ValueError("Cloud Run returned no valid text.")

        db = SessionLocal()
        try:
            # PURE ORM UPDATE (Matches exactly to your model)
            analysis = db.query(TestAnalysis).filter(TestAnalysis.test_id == test_id).first()
            if analysis:
                analysis.status = 'COMPLETED'
                analysis.analysis_text = stitched_markdown
                analysis.timestamp = aware_utcnow()

            stmt = insert(TestDocuments).values(
                id=str(uuid.uuid4()), test_id=test_id, drive_file_id=f"analysis_{test_id}",
                file_name=f"LLM_Vulnerability_Analysis_{test_name}.md",
                mime_type='text/markdown', file_url=f"{BASE_URL}/tests/{test_id}/analysis", doc_type='LLM_ANALYSIS',
                last_modified=aware_utcnow(), synced_at=aware_utcnow(), is_virtual=True
            ).on_conflict_do_update(
                index_elements=['drive_file_id'],
                set_={'file_name': f"LLM_Vulnerability_Analysis_{test_name}.md", 'last_modified': aware_utcnow(),
                      'synced_at': aware_utcnow()}
            )
            db.execute(stmt)

            stmt_mile = insert(TestMilestone).values(
                id=str(uuid.uuid4()), test_id=test_id, step_name='Validate Finding', is_completed=True
            ).on_conflict_do_update(index_elements=['test_id', 'step_name'], set_={'is_completed': True})
            db.execute(stmt_mile)

            db.commit()
        finally:
            db.close()

        try:
            await asyncio.to_thread(process_test_documents_background, test_id, user_id, "admin")
        except Exception:
            pass

        db = SessionLocal()
        try:
            db.add(Notifications(id=str(uuid.uuid4()), user_id=user_id, message=f"Analysis for '{test_name}' is ready!",
                                 type="SUCCESS", created_at=aware_utcnow()))
            db.commit()
        finally:
            db.close()

        await manager.broadcast(json.dumps(
            {"action": "REPORT_READY", "email": user_email, "message": f"Analysis ready!",
             "link": f"/tests/{test_id}/analysis"}))

    except Exception as e:
        db = SessionLocal()
        try:
            # PURE ORM ERROR UPDATE
            analysis_error = db.query(TestAnalysis).filter(TestAnalysis.test_id == test_id).first()
            if analysis_error:
                analysis_error.status = 'FAILED'
                analysis_error.timestamp = aware_utcnow()
                db.commit()
        finally:
            db.close()

        await manager.broadcast(
            json.dumps({"action": "REPORT_FAILED", "email": user_email, "message": f"Analysis failed: {str(e)}"}))

def process_bulk_tests_background(asset_ids, user_id: str, role: str, service_lane_id: str = None):
    tests_to_provision = []
    db = SessionLocal()
    try:
        for asset_id in asset_ids:
            query = (db.query(
                RawAssets.name, RawAssets.service_forecast_id, ServiceLanes.default_credits,
                ServiceLanes.default_duration_weeks, ServiceLanes.name.label("service_name"),
                Country.name.label("country_name"), ServiceLanes.auto_provision_workspace, RawAssets.category_id)
                     .select_from(Assets)
                     .join(RawAssets, Assets.raw_asset_id == RawAssets.id)
                     .outerjoin(ServiceLanes, RawAssets.service_forecast_id == ServiceLanes.id)
                     .outerjoin(Country, RawAssets.country_id == Country.id)
                     .filter(Assets.id == str(asset_id)))

            if role == 'maintainer':
                query = query.filter(RawAssets.service_forecast_id == (
                    str(service_lane_id) if service_lane_id else '00000000-0000-0000-0000-000000000000'))

            # Filter where (duplicate allowed OR test doesn't exist in active state)
            active_test_exists = (db.query(TestAssets.test_id)
                                  .join(Tests, TestAssets.test_id == Tests.id)
                                  .filter(TestAssets.asset_id == Assets.id, Tests.stages.in_([TestStages.NOT_PLANNED, TestStages.SCHEDULED, TestStages.IN_PROGRESS]))
                                  .exists())

            query = query.filter(or_(RawAssets.duplicate_allowed == True, ~active_test_exists))
            asset_data = query.first()

            if not asset_data or not asset_data.service_forecast_id: continue

            new_test_id = str(uuid.uuid4())
            new_test = Tests(
                id=new_test_id, name=asset_data.name, service_lane_id=str(asset_data.service_forecast_id),
                category_id=str(asset_data.category_id) if asset_data.category_id else None,
                credits_per_week=float(asset_data.default_credits or 2.0),
                duration_weeks=int(asset_data.default_duration_weeks or 1),
                stages=TestStages.NOT_PLANNED
            )
            db.add(new_test)
            db.add(TestAssets(test_id=new_test_id, asset_id=str(asset_id)))

            log_test_history(db, new_test_id, user_id, "GENERATED", f"Test generated from Asset Pool.")
            log_audit_event(user_id=user_id, role=role, action="TEST_CREATED", resource_type="TESTS",
                            resource_id=new_test_id, details=f"Bulk created test for {asset_data.name}.")

            tests_to_provision.append(
                (new_test_id, datetime.now().year, asset_data.service_name, asset_data.country_name, asset_data.name,
                 asset_data.auto_provision_workspace))

        db.commit()
    finally:
        db.close()

    for test_id, year, s_name, c_name, t_name, auto_prov in tests_to_provision:
        if auto_prov: DriveManager().provision_test_workspace(test_id, year, s_name, c_name, t_name)


# --- ENDPOINTS LOGIC ---
def create_test(db: Session, t, current_user: dict):
    verify_lane_access(current_user, str(t.service_lane_id))
    new_test_id = str(uuid.uuid4())
    cat_id = str(t.category_id) if t.category_id else None

    new_test = Tests(
        id=new_test_id, name=t.name, service_lane_id=str(t.service_lane_id), category_id=cat_id,
        credits_per_week=t.credits_per_week, duration_weeks=t.duration_weeks, stages=TestStages.NOT_PLANNED
    )
    db.add(new_test)

    for asset_id in t.asset_ids:
        db.add(TestAssets(test_id=new_test_id, asset_id=str(asset_id)))

    log_test_history(db, new_test_id, current_user['id'], "CREATED", "Test manually created.")
    db.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_CREATED", "TESTS", new_test_id,
                    f"Test {t.name} created.")
    return {"message": "Test created successfully", "id": new_test_id}


def get_all_tests(db: Session, current_user: dict):
    # Scalar Subqueries for aggregate strings and existence checks
    assigned_pentesters_sq = (db.query(func.coalesce(func.string_agg(func.distinct(Users.name), ', '), 'Unassigned'))
                              .join(Assignments, Users.id == Assignments.user_id)
                              .filter(Assignments.test_id == Tests.id).scalar_subquery())

    has_secret_sq = db.query(SecretNotes.test_id).filter(SecretNotes.test_id == Tests.id).exists()

    # Pre-join subquery for finding the primary raw asset and details
    asset_sq = (db.query(
        TestAssets.test_id,
        Assets.raw_asset_id,
        RawAssets.is_kpi,
        RawAssets.is_critical,
        AssetTypes.name.label('asset_type_name'))
                .join(Assets, TestAssets.asset_id == Assets.id)
                .join(RawAssets, Assets.raw_asset_id == RawAssets.id)
                .outerjoin(AssetTypes, RawAssets.asset_type_id == AssetTypes.id)
                .distinct(TestAssets.test_id).subquery())  # Ensures limit 1 per test

    query = (db.query(
        Tests.id, Tests.name, Tests.start_week, Tests.start_year, Tests.duration_weeks,
        Tests.stages, ServiceLanes.name.label("service_lane_name"),
        ServiceLanes.is_active.label("is_service_active"), ServiceLanes.auto_provision_workspace,
        ServiceCategories.name.label("category_name"),
        assigned_pentesters_sq.label('assigned_pentesters'),
        has_secret_sq.label('has_secret'),
        Tests.drive_folder_url, Tests.kiss24,
        asset_sq.c.raw_asset_id, asset_sq.c.is_kpi, asset_sq.c.is_critical, asset_sq.c.asset_type_name)
             .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
             .outerjoin(ServiceCategories, Tests.category_id == ServiceCategories.id)
             .outerjoin(asset_sq, Tests.id == asset_sq.c.test_id))

    if current_user.get('role') == 'maintainer':
        query = query.filter(
            Tests.service_lane_id == str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    query = query.order_by(Tests.start_year.desc().nullslast(), Tests.start_week.desc().nullslast(), Tests.name.asc())
    rows = query.all()

    return [{
        "id": str(r.id), "name": r.name, "start_week": r.start_week, "start_year": r.start_year,
        "duration_weeks": r.duration_weeks, "status": r.stages.name if r.stages else None,
        "service_lane_name": r.service_lane_name, "is_service_active": r.is_service_active,
        "auto_provision_workspace": r.auto_provision_workspace, "category_name": r.category_name,
        "assigned_pentesters": r.assigned_pentesters, "has_secret": r.has_secret,
        "drive_folder_url": r.drive_folder_url, "kiss24": r.kiss24,
        "raw_asset_id": str(r.raw_asset_id) if r.raw_asset_id else None,
        "is_kpi": r.is_kpi, "is_critical": r.is_critical, "asset_type_name": r.asset_type_name
    } for r in rows]


def get_test_details(db: Session, test_id: str, current_user: dict):
    assigned_pentesters_sq = (db.query(func.coalesce(func.string_agg(func.distinct(Users.name), ', '), 'Unassigned'))
                              .join(Assignments, Users.id == Assignments.user_id)
                              .filter(Assignments.test_id == Tests.id).scalar_subquery())

    has_secret_sq = db.query(SecretNotes.test_id).filter(SecretNotes.test_id == Tests.id).exists()

    query = (db.query(
        Tests.id, Tests.name, Tests.service_lane_id, Tests.credits_per_week, Tests.duration_weeks,
        Tests.stages, Tests.start_week, Tests.start_year, Tests.is_tentative, Tests.kiss24,
        Tests.drive_folder_id, Tests.drive_folder_url, ServiceLanes.name.label("service_lane_name"),
        ServiceLanes.auto_provision_workspace, Country.kiss24_uuid.label("country_kiss24_uuid"),
        has_secret_sq.label('has_secret'), assigned_pentesters_sq.label('assigned_pentesters'),
        RawAssets.category_id, ServiceCategories.name.label("category_name"))
             .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
             .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
             .outerjoin(Assets, TestAssets.asset_id == Assets.id)
             .outerjoin(RawAssets, Assets.raw_asset_id == RawAssets.id)
             .outerjoin(ServiceCategories, RawAssets.category_id == ServiceCategories.id)
             .outerjoin(Country, RawAssets.country_id == Country.id)
             .filter(Tests.id == test_id))

    if current_user.get('role') == 'maintainer':
        query = query.filter(
            Tests.service_lane_id == str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    test_row = query.first()
    if not test_row: raise HTTPException(status_code=404, detail="Test not found")

    test_data = {
        "id": str(test_row.id), "name": test_row.name, "service_lane_id": str(test_row.service_lane_id),
        "credits_per_week": test_row.credits_per_week, "duration_weeks": test_row.duration_weeks,
        "status": test_row.stages.name if test_row.stages else None, "start_week": test_row.start_week,
        "start_year": test_row.start_year, "is_tentative": test_row.is_tentative, "kiss24": test_row.kiss24,
        "drive_folder_id": test_row.drive_folder_id, "drive_folder_url": test_row.drive_folder_url,
        "service_lane_name": test_row.service_lane_name, "auto_provision_workspace": test_row.auto_provision_workspace,
        "country_kiss24_uuid": test_row.country_kiss24_uuid, "has_secret": test_row.has_secret,
        "assigned_pentesters": test_row.assigned_pentesters,
        "category_id": str(test_row.category_id) if test_row.category_id else None,
        "category_name": test_row.category_name
    }

    # Assets
    assets_db = (db.query(
        Assets.id.label("asset_id"), Assets.raw_asset_id, RawAssets.name.label("asset_name"),
        RawAssets.country_id, RawAssets.kiss24_asset_id)
                 .join(TestAssets, Assets.id == TestAssets.asset_id)
                 .join(RawAssets, Assets.raw_asset_id == RawAssets.id)
                 .filter(TestAssets.test_id == test_id).all())

    test_data["assets"] = [{
        "asset_id": str(a.asset_id), "raw_asset_id": str(a.raw_asset_id) if a.raw_asset_id else None,
        "asset_name": a.asset_name, "country_id": str(a.country_id) if a.country_id else None,
        "kiss24_asset_id": a.kiss24_asset_id
    } for a in assets_db]

    raw_asset_ids = [str(a['raw_asset_id']) for a in test_data["assets"] if a['raw_asset_id']]
    country_ids = [str(a['country_id']) for a in test_data["assets"] if a['country_id']]

    # Contacts
    test_data["asset_contacts"] = []
    if raw_asset_ids:
        rac = (db.query(Contacts.id.label("contact_id"), Contacts.email, Contacts.full_name, RawAssetContacts.is_stakeholder, RawAssetContacts.is_developer)
               .join(RawAssetContacts, Contacts.id == RawAssetContacts.contact_id)
               .filter(RawAssetContacts.raw_asset_id.in_(raw_asset_ids))
               .distinct()
               .order_by(Contacts.email.asc()).all())
        test_data["asset_contacts"] = [{"contact_id": str(c.contact_id), "email": c.email, "full_name": c.full_name,
                                        "is_stakeholder": c.is_stakeholder, "is_developer": c.is_developer} for c in
                                       rac]

    test_data["country_contacts"] = []
    if country_ids:
        cc = (db.query(Contacts.id.label("contact_id"), Contacts.email, Contacts.full_name, CountryContacts.is_stakeholder, CountryContacts.is_developer)
              .join(CountryContacts, Contacts.id == CountryContacts.contact_id)
              .filter(CountryContacts.country_id.in_(country_ids)).distinct().order_by(Contacts.email.asc()).all())
        test_data["country_contacts"] = [{"contact_id": str(c.contact_id), "email": c.email, "full_name": c.full_name,
                                          "is_stakeholder": c.is_stakeholder, "is_developer": c.is_developer} for c in
                                         cc]

    # History
    hist = (db.query(TestHistory.id, TestHistory.action, TestHistory.details, TestHistory.timestamp, Users.name.label("user_name"))
            .outerjoin(Users, TestHistory.user_id == Users.id)
            .filter(TestHistory.test_id == test_id).order_by(TestHistory.timestamp.desc()).all())
    test_data["history"] = [
        {"id": str(h.id), "action": h.action, "details": h.details, "timestamp": h.timestamp, "user_name": h.user_name}
        for h in hist]

    return test_data


def update_test(db: Session, test_id: str, t, current_user: dict, background_tasks):
    verify_lane_access(current_user, str(t.service_lane_id))

    old_data = (db.query(Tests.drive_folder_id, ServiceLanes.name, Country.name, Tests.start_year)
                .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
                .outerjoin(Assets, TestAssets.asset_id == Assets.id)
                .outerjoin(Country, Assets.country_id == Country.id)
                .filter(Tests.id == test_id).first())

    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found")

    db_stage = FRONTEND_TO_DB_STAGES.get(t.status, TestStages.NOT_PLANNED)
    if db_stage == TestStages.NOT_PLANNED:
        db.query(Assignments).filter(Assignments.test_id == test_id).delete()
        test.start_week = None
        test.start_year = None

    cat_id = str(t.category_id) if hasattr(t, 'category_id') and t.category_id else None
    kiss24_val = str(t.kiss24) if hasattr(t, 'kiss24') and t.kiss24 else None

    test.name = t.name
    test.service_lane_id = str(t.service_lane_id)
    test.category_id = cat_id
    test.credits_per_week = t.credits_per_week
    test.duration_weeks = t.duration_weeks
    test.stages = db_stage
    test.is_tentative = t.is_tentative
    test.kiss24 = kiss24_val

    # Update raw assets category
    raw_asset_ids = db.query(Assets.raw_asset_id).join(TestAssets, Assets.id == TestAssets.asset_id).filter(
        TestAssets.test_id == test_id).subquery()
    db.query(RawAssets).filter(RawAssets.id.in_(raw_asset_ids)).update({"category_id": cat_id},
                                                                       synchronize_session=False)

    log_test_history(db, test_id, current_user['id'], "UPDATED",
                     f"Settings updated: {t.credits_per_week}cr, {t.duration_weeks}wks.")
    db.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_UPDATED", "TESTS", test_id, "Updated.")

    if old_data and old_data[0]:
        new_service_name = db.query(ServiceLanes.name).filter(ServiceLanes.id == str(t.service_lane_id)).scalar()
        background_tasks.add_task(background_relocate_workspace, old_data[0],
                                  t.start_year or old_data[3] or datetime.now().year, new_service_name,
                                  old_data[2] or "General", t.name)

    return {"message": "Test updated successfully."}


def delete_test(db: Session, test_id: str, current_user: dict, background_tasks):
    test_data = db.query(Tests.name, Tests.drive_folder_id, Tests.service_lane_id).filter(Tests.id == test_id).first()
    if not test_data: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test_data[2]))

    log_test_history(db, test_id, current_user['id'], "DELETED", "Test permanently deleted and assets freed.")

    db.flush()

    db.query(TestAssets).filter(TestAssets.test_id == test_id).delete()
    db.query(Assignments).filter(Assignments.test_id == test_id).delete()
    db.query(Tests).filter(Tests.id == test_id).delete()
    db.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_DELETED", "TESTS", test_id, "Deleted.")
    if test_data and test_data[1]:
        background_tasks.add_task(background_archive_workspace, test_data[1], test_data[0])

    return {"message": "Test permanently deleted and assets freed."}


def provision_workspace_manually(db: Session, test_id: str, current_user: dict, background_tasks):
    query = (db.query(Tests.name, ServiceLanes.name.label("s_name"), Country.name.label("c_name"), Tests.start_year)
             .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
             .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
             .outerjoin(Assets, TestAssets.asset_id == Assets.id)
             .outerjoin(Country, Assets.country_id == Country.id)
             .filter(Tests.id == test_id))

    if current_user.get('role') == 'maintainer':
        query = query.filter(
            Tests.service_lane_id == str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    test_data = query.first()
    if not test_data: raise HTTPException(status_code=404, detail="Test not found.")

    background_tasks.add_task(background_provision_workspace, test_id, test_data.start_year or datetime.now().year,
                              test_data.s_name, test_data.c_name, test_data.name)
    log_audit_event(str(current_user["id"]), current_user["role"], "PROVISIONING_WORKSPACE", "TESTS", test_id,
                    "Provisioned.")
    return {"message": "Workspace provisioning started."}


def toggle_tentative(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test.service_lane_id))

    test.is_tentative = not test.is_tentative
    state_str = "Marked as Tentative (TBC)" if test.is_tentative else "Removed Tentative mark"
    log_test_history(db, test_id, current_user['id'], "UPDATED", state_str)
    db.commit()
    return {"message": state_str}


def schedule_test(db: Session, test_id: str, schedule, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test.service_lane_id))

    if test.start_week is not None and test.start_year is not None and (
            test.start_week != schedule.start_week or test.start_year != schedule.start_year):
        assignments = db.query(Assignments.user_id).filter(Assignments.test_id == test_id).distinct().all()
        for (u_id,) in assignments:
            db.add(Notifications(id=str(uuid.uuid4()), user_id=str(u_id),
                                 message=f"Removed from {test.name} (rescheduled).", type="REMOVAL",
                                 created_at=aware_utcnow()))
        db.query(Assignments).filter(Assignments.test_id == test_id).delete()
        log_test_history(db, test_id, current_user['id'], "UNASSIGNED", "Pentesters removed due to schedule shift.")

    test.start_week = schedule.start_week
    test.start_year = schedule.start_year
    test.stages = TestStages.SCHEDULED
    log_test_history(db, test_id, current_user['id'], "SCHEDULED",
                     f"Scheduled Wk {schedule.start_week}, {schedule.start_year}.")
    db.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_SCHEDULED", "TESTS", test_id, "Scheduled.")
    return {"message": "Test scheduled on the board."}


def unschedule_test(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found.")
    verify_lane_access(current_user, str(test.service_lane_id))

    assignments = db.query(Assignments.user_id).filter(Assignments.test_id == test_id).all()
    for (u_id,) in assignments:
        db.add(
            Notifications(id=str(uuid.uuid4()), user_id=str(u_id), message=f"Removed from {test.name} (unscheduled).",
                          type="REMOVAL", created_at=aware_utcnow()))

    db.query(Assignments).filter(Assignments.test_id == test_id).delete()
    test.start_week = None
    test.start_year = None
    test.stages = TestStages.NOT_PLANNED
    log_test_history(db, test_id, current_user['id'], "UNSCHEDULED", "Returned to backlog.")
    db.commit()
    log_audit_event(str(current_user["id"]), current_user["role"], "TEST_UNSCHEDULED", "TESTS", test_id, "Unscheduled.")
    return {"message": "Test returned to backlog."}


def complete_test(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found")
    verify_lane_access(current_user, str(test.service_lane_id))

    test.stages = TestStages.COMPLETED
    log_test_history(db, test_id, current_user['id'], "COMPLETED", "Marked as completed.")
    db.commit()
    return {"message": "Test marked as Completed."}


def mark_test_unable(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if not test: raise HTTPException(status_code=404, detail="Test not found.")
    verify_lane_access(current_user, str(test.service_lane_id))

    test.stages = TestStages.STOPPED
    test.name = f"[BLOCKED] {test.name}"
    db.query(Assignments).filter(Assignments.test_id == test_id).delete()

    clone_id = str(uuid.uuid4())
    clone_test = Tests(
        id=clone_id, name=test.name.replace("[BLOCKED] ", ""), service_lane_id=str(test.service_lane_id),
        credits_per_week=test.credits_per_week, duration_weeks=test.duration_weeks, stages=TestStages.NOT_PLANNED
    )
    db.add(clone_test)
    db.flush()

    assets = db.query(TestAssets.asset_id).filter(TestAssets.test_id == test_id).all()
    for (a_id,) in assets:
        db.add(TestAssets(test_id=clone_id, asset_id=str(a_id)))

    history = db.query(TestHistory).filter(TestHistory.test_id == test_id).all()
    for h in history:
        db.add(
            TestHistory(id=str(uuid.uuid4()), test_id=clone_id, user_id=h.user_id, action=h.action, details=h.details,
                        timestamp=h.timestamp))

    log_test_history(db, clone_id, current_user['id'], "CLONED", "Resumed in backlog.")
    log_test_history(db, test_id, current_user['id'], "STOPPED", f"Clone generated: {clone_id}")
    db.commit()
    return {"message": "Test marked as Stopped."}


def unstop_test(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id, Tests.stages == TestStages.STOPPED).first()
    if not test: raise HTTPException(status_code=404, detail="Stopped test not found.")
    verify_lane_access(current_user, str(test.service_lane_id))

    original_name = test.name.replace("[BLOCKED] ", "") if test.name.startswith("[BLOCKED] ") else test.name

    hist = db.query(TestHistory.details).filter(TestHistory.test_id == test_id,
                                                TestHistory.action == 'STOPPED').order_by(
        TestHistory.timestamp.desc()).first()
    if hist and "Clone generated: " in hist[0]:
        clone_id = hist[0].split("Clone generated: ")[1].strip()
        clone_test = db.query(Tests).filter(Tests.id == clone_id).first()
        if clone_test:
            if clone_test.stages == TestStages.NOT_PLANNED:
                db.query(TestAssets).filter(TestAssets.test_id == clone_id).delete()
                db.delete(clone_test)
            else:
                raise HTTPException(status_code=400, detail="Cannot Undo Stop: The clone is already scheduled.")

    test.name = original_name
    test.stages = TestStages.SCHEDULED
    log_test_history(db, test_id, current_user['id'], "UNSTOPPED", "Unblocked and clone removed.")
    db.commit()
    return {"message": "Test unstopped successfully."}


def uncomplete_test(db: Session, test_id: str, current_user: dict):
    test = db.query(Tests).filter(Tests.id == test_id).first()
    if test:
        verify_lane_access(current_user, str(test.service_lane_id))
        test.stages = TestStages.SCHEDULED
        log_test_history(db, test_id, current_user['id'], "UNCOMPLETED", "Reverted to Scheduled.")
        db.commit()
        return {"message": "Test uncompleted."}
    raise HTTPException(status_code=404, detail="Test not found")


def create_assignment(db: Session, assign, current_user: dict):
    existing = db.query(Assignments).filter(Assignments.user_id == str(assign.user_id),
                                            Assignments.week_number == assign.week_number,
                                            Assignments.year == assign.year,
                                            Assignments.test_id == str(assign.test_id)).first()
    if existing: raise HTTPException(status_code=400, detail="Already assigned for this week!")

    new_assign = Assignments(id=str(uuid.uuid4()), test_id=str(assign.test_id), user_id=str(assign.user_id),
                             week_number=assign.week_number, year=assign.year,
                             allocated_credits=assign.allocated_credits)
    db.add(new_assign)

    test_name = db.query(Tests.name).filter(Tests.id == str(assign.test_id)).scalar()
    if test_name:
        db.add(Notifications(id=str(uuid.uuid4()), user_id=str(assign.user_id),
                             message=f"Assigned to {test_name} Wk {assign.week_number}.", type="ASSIGNMENT",
                             created_at=aware_utcnow()))

    user_name = db.query(Users.name).filter(Users.id == str(assign.user_id)).scalar() or 'Unknown'
    log_test_history(db, str(assign.test_id), current_user['id'], "ASSIGNED",
                     f"Assigned {user_name} for Wk {assign.week_number}.")
    db.commit()
    return {"message": "Successfully Assigned"}


def remove_assignment(db: Session, test_id: str, user_id: str, current_user: dict):
    test_name = db.query(Tests.name).filter(Tests.id == test_id).scalar()
    if test_name:
        db.add(Notifications(id=str(uuid.uuid4()), user_id=str(user_id), message=f"Removed from {test_name}.",
                             type="REMOVAL", created_at=aware_utcnow()))

    db.query(Assignments).filter(Assignments.test_id == test_id, Assignments.user_id == user_id).delete()
    user_name = db.query(Users.name).filter(Users.id == user_id).scalar() or 'Unknown'
    log_test_history(db, test_id, current_user['id'], "UNASSIGNED", f"Removed {user_name}.")
    db.commit()
    return {"message": "Successfully Unassigned"}


def get_test_history(db: Session, test_id: str, current_user: dict):
    query = (db.query(TestHistory.id, TestHistory.action, TestHistory.details, TestHistory.timestamp, Users.name.label("user_name"))
             .outerjoin(Users, TestHistory.user_id == Users.id)
             .filter(TestHistory.test_id == test_id))

    if current_user.get('role') == 'maintainer':
        query = query.join(Tests, TestHistory.test_id == Tests.id).filter(
            Tests.service_lane_id == str(current_user.get('service_lane_id') or '00000000-0000-0000-0000-000000000000'))

    hist = query.order_by(TestHistory.timestamp.desc()).all()
    return [
        {"id": str(h.id), "action": h.action, "details": h.details, "timestamp": h.timestamp, "user_name": h.user_name}
        for h in hist]


def get_test_secret(db: Session, test_id: str, current_user: dict):
    if current_user.get('role') not in ['admin', 'pentester']: raise HTTPException(status_code=403,
                                                                                   detail="No access to Secure Notes.")

    note = db.query(SecretNotes.encrypted_data).filter(SecretNotes.test_id == test_id).first()
    if not note: return {"exists": False}

    key = db.query(SecretNoteAccess.encrypted_key).filter(SecretNoteAccess.test_id == test_id,
                                                          SecretNoteAccess.user_id == str(current_user["id"])).first()
    shared = db.query(SecretNoteAccess.user_id).filter(SecretNoteAccess.test_id == test_id).all()

    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_FETCHED", "TEST_SECRET",
                    details=f"Fetched secret {test_id}.")
    return {"exists": True, "encrypted_data": note.encrypted_data, "encrypted_key": key.encrypted_key if key else None,
            "shared_with": [str(r.user_id) for r in shared]}


def update_test_secret(db: Session, test_id: str, payload: dict, current_user: dict):
    if current_user.get('role') not in ['admin', 'pentester']: raise HTTPException(status_code=403, detail="No access.")

    stmt = (insert(SecretNotes).values(test_id=test_id, encrypted_data=payload.get("encrypted_data"),
                                      updated_at=aware_utcnow())
            .on_conflict_do_update(index_elements=['test_id'],
                               set_={'encrypted_data': payload.get("encrypted_data"), 'updated_at': aware_utcnow()}))
    db.execute(stmt)

    db.query(SecretNoteAccess).filter(SecretNoteAccess.test_id == test_id).delete()
    for access in payload.get("access_list", []):
        db.add(SecretNoteAccess(test_id=test_id, user_id=access["user_id"], encrypted_key=access["encrypted_key"]))

    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_UPDATED", "TEST_SECRET",
                    details=f"Updated secret {test_id}.")
    db.commit()
    return {"message": "Secure note vaulted."}


def delete_test_secret(db: Session, test_id: str, current_user: dict):
    if current_user.get('role') not in ['admin', 'pentester']: raise HTTPException(status_code=403, detail="No access.")
    db.query(SecretNotes).filter(SecretNotes.test_id == test_id).delete()
    log_audit_event(str(current_user["id"]), current_user["name"], "SECRET_DELETED", "TEST_SECRET",
                    details=f"Deleted secret {test_id}.")
    db.commit()
    return {"message": "Secure note deleted."}


def get_milestones(db: Session, test_id: str, current_user: dict):
    lane_id = db.query(Tests.service_lane_id).filter(Tests.id == test_id).scalar()
    if lane_id:
        verify_lane_access(current_user, str(lane_id))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")

    milestones = db.query(TestMilestone.step_name, TestMilestone.is_completed).filter(
        TestMilestone.test_id == test_id).all()
    return {m.step_name: m.is_completed for m in milestones}


def update_milestone(db: Session, test_id: str, payload, current_user: dict):
    lane_id = db.query(Tests.service_lane_id).filter(Tests.id == test_id).scalar()
    if lane_id:
        verify_lane_access(current_user, str(lane_id))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")

    stmt = insert(TestMilestone).values(
        id=str(uuid.uuid4()), test_id=test_id, step_name=payload.step_name, is_completed=payload.is_completed
    ).on_conflict_do_update(
        index_elements=['test_id', 'step_name'], set_={'is_completed': payload.is_completed}
    )
    db.execute(stmt)
    db.commit()
    return {"message": "Updated"}


def get_requirements(db: Session, test_id: str, current_user: dict):
    lane_id = db.query(Tests.service_lane_id).filter(Tests.id == test_id).scalar()
    if lane_id:
        verify_lane_access(current_user, str(lane_id))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")

    reqs = db.query(TestRequirement.id, TestRequirement.description, TestRequirement.is_completed).filter(
        TestRequirement.test_id == test_id).order_by(TestRequirement.id.asc()).all()
    return [{"id": str(r.id), "description": r.description, "is_completed": r.is_completed} for r in reqs]


def add_requirement(db: Session, test_id: str, req, current_user: dict):
    lane_id = db.query(Tests.service_lane_id).filter(Tests.id == test_id).scalar()
    if lane_id:
        verify_lane_access(current_user, str(lane_id))
    else:
        raise HTTPException(status_code=404, detail="Test not found.")

    new_req = TestRequirement(id=str(uuid.uuid4()), test_id=test_id, description=req.description, is_completed=False)
    db.add(new_req)
    db.commit()
    return {"id": str(new_req.id), "description": req.description, "is_completed": False}


def delete_requirement(db: Session, req_id: str, current_user: dict):
    req_data = db.query(TestRequirement.test_id, Tests.service_lane_id).join(Tests,
                                                                              TestRequirement.test_id == Tests.id).filter(
        TestRequirement.id == req_id).first()
    if not req_data: raise HTTPException(status_code=404, detail="Not found.")
    verify_lane_access(current_user, str(req_data.service_lane_id))

    db.query(TestRequirement).filter(TestRequirement.id == req_id).delete()
    db.commit()
    return {"message": "Deleted"}


def toggle_requirement(db: Session, req_id: str, current_user: dict):
    req = db.query(TestRequirement).filter(TestRequirement.id == req_id).first()
    if not req: raise HTTPException(status_code=404, detail="Not found.")

    lane_id = db.query(Tests.service_lane_id).filter(Tests.id == req.test_id).scalar()
    verify_lane_access(current_user, str(lane_id))

    # 1. Update the state in Python memory
    req.is_completed = not req.is_completed
    new_status = req.is_completed

    # 2. FLUSH THE STATE TO THE DB (The magic fix!)
    db.flush()

    # 3. Now the DB query will see the correct, updated counts
    total_reqs, completed_reqs = db.query(
        func.count(TestRequirement.id),
        func.sum(case((TestRequirement.is_completed == True, 1), else_=0))
    ).filter(TestRequirement.test_id == req.test_id).first()

    if total_reqs > 0 and total_reqs == completed_reqs:
        stmt = (insert(TestMilestone).values(id=str(uuid.uuid4()), test_id=req.test_id, step_name='Requirements', is_completed=True)
                .on_conflict_do_update(index_elements=['test_id', 'step_name'], set_={'is_completed': True}))
        db.execute(stmt)
    else:
        db.query(TestMilestone).filter(TestMilestone.test_id == req.test_id,
                                        TestMilestone.step_name == 'Requirements').update({'is_completed': False})

    db.commit()
    return {"is_completed": new_status, "all_completed": total_reqs == completed_reqs}