from fastapi import APIRouter, Depends, HTTPException, status
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
from audit_logger import log_audit_event
from sqlalchemy.testing.pickleable import User
from utils.timeaware import aware_utcnow
from utils.kiss24_service import (
    map_asset_onetrust_custom_field,
    map_organizations,
    create_test,
    get_test_info,
    get_test_vulns_info,
    add_snowid_to_kiss24asset,
    sync_vuln_type_kiss24,
    map_mario_user_kiss24_uuid
)
from utils.security_cipher import get_cipher
from datetime import datetime

router = APIRouter(prefix="/api/kiss24", tags=["Kiss24"])


@router.post("/sync-org-ids", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_org_ids(
        current_user: dict = Depends(require_admin),
        cursor=Depends(get_db_cursor)
):
    """
    Admin-only endpoint to sync KISS24 organization UUIDs with Country.
    """
    try:
        orgs_map = map_organizations()
        if not orgs_map:
            return {
                "status": "Success",
                "message": "No Organization mappings found in KISS24.",
                "total_kiss24_mapped": 0,
                "total_countries_updated": 0
            }

        cursor.execute("""
            SELECT id, code FROM countries
            WHERE code IS NOT NULL
        """)
        rows = cursor.fetchall()

        matched_count = 0
        updated_countries = []

        for id, code in rows:
            if not code:
                continue

            clean_country_code = str(code).strip()
            if clean_country_code in orgs_map:
                kiss24_uuid = orgs_map[clean_country_code]

                cursor.execute("""
                    UPDATE countries SET kiss24_uuid = %s WHERE id = %s
                """, (kiss24_uuid, str(id)))

                matched_count += 1
                updated_countries.append({
                    "id": str(id),
                    "code": clean_country_code,
                    "kiss24_org_uuid": kiss24_uuid,
                })

        cursor.connection.commit()
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="KISS24_COUNTRY_SYNC",
            resource_type="KISS24",
            resource_id="N/A",
            details=f"Synced {matched_count} Countries with KISS24 asset UUIDs.",
        )

        return {
            "status": "Success",
            "message": f"Successfully updated {matched_count} raw assets with KISS24 Asset IDs.",
            "total_kiss24_mapped": len(orgs_map),
            "total_raw_assets_updated": matched_count,
            "updated_assets": updated_countries
        }

    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync KISS24 Countries IDs: {str(e)}"
        )


@router.post("/sync-asset-ids", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_asset_ids(
        current_user: dict = Depends(require_admin),
        cursor=Depends(get_db_cursor)
):
    """
    Admin-only endpoint to sync KISS24 asset UUIDs with Raw Assets.
    """
    try:
        # 1. Fetch OneTrust ID -> KISS24 Asset UUID mapping dict from KISS24
        onetrust_map = map_asset_onetrust_custom_field()

        if not onetrust_map:
            return {
                "status": "Success",
                "message": "No OneTrust asset mappings found in KISS24.",
                "total_kiss24_mapped": 0,
                "total_raw_assets_updated": 0
            }

        # 2. Query raw_assets joined with snow_metadata that have a u_onetrust_number
        cursor.execute("""
            SELECT r.id, s.snow_data->>'u_onetrust_number' AS onetrust_id
            FROM raw_assets r
            JOIN raw_assets_snow_metadata s ON r.id = s.correlation_id
            WHERE s.snow_data->>'u_onetrust_number' IS NOT NULL
              AND s.snow_data->>'u_onetrust_number' != ''
        """)
        rows = cursor.fetchall()

        matched_count = 0
        updated_assets = []

        # 3. Match and update kiss24_asset_id in database
        for raw_asset_id, onetrust_id in rows:
            if not onetrust_id:
                continue

            clean_onetrust_id = str(onetrust_id).strip()

            if clean_onetrust_id in onetrust_map:
                kiss24_uuid = onetrust_map[clean_onetrust_id]

                cursor.execute("""
                    UPDATE raw_assets
                    SET kiss24_asset_id = %s,
                        update_date = NOW()
                    WHERE id = %s
                """, (kiss24_uuid, str(raw_asset_id)))

                matched_count += 1
                updated_assets.append({
                    "raw_asset_id": str(raw_asset_id),
                    "onetrust_id": clean_onetrust_id,
                    "kiss24_asset_id": kiss24_uuid
                })

        # Commit changes to PostgreSQL
        cursor.connection.commit()

        # 4. Log audit trail
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="KISS24_ASSET_SYNC",
            resource_type="KISS24",
            resource_id="N/A",
            details=f"Synced {matched_count} Raw Assets with KISS24 asset UUIDs.",
        )

        return {
            "status": "Success",
            "message": f"Successfully updated {matched_count} raw assets with KISS24 Asset IDs.",
            "total_kiss24_mapped": len(onetrust_map),
            "total_raw_assets_updated": matched_count,
            "updated_assets": updated_assets
        }

    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync KISS24 Asset IDs: {str(e)}"
        )


@router.post("/sync-update-kiss24-snowid", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_update_kiss24_snowid(
        current_user: dict = Depends(require_admin),
        cursor=Depends(get_db_cursor)
):
    """
    Admin-only endpoint to Update the Custom Field 'Service Now ID' of Assets in KISS24 with the known value.
    """

    # 1. Fetch assets excluding NULLs and empty strings
    cursor.execute("""
        SELECT kiss24_asset_id, snow_number
        FROM raw_assets
        WHERE kiss24_asset_id IS NOT NULL AND kiss24_asset_id != ''
          AND snow_number IS NOT NULL AND snow_number != ''
    """)
    rows = cursor.fetchall()

    if not rows:
        return {"message": "No eligible assets found to sync.", "results": None}

    # 2. Build the dictionary payload
    asset_dict_payload = {row[0]: row[1] for row in rows}

    try:
        # 3. Call the helper function
        sync_results = add_snowid_to_kiss24asset(asset_dict_payload)

        # 4. Log the audit event
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="KISS24_SNOW_ID_SYNC",
            resource_type="KISS24",
            resource_id="N/A",
            details=f"Pushed ServiceNow IDs to KISS24. Success: {sync_results['success_count']}, Failed: {sync_results['failed_count']}."
        )

        return {
            "message": f"Sync complete. Successfully updated {sync_results['success_count']} assets.",
            "results": sync_results
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during sync: {str(e)}"
        )


@router.post("/sync-vuln-types", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_kiss24_vulnerability_types(
        current_user: dict = Depends(require_admin),
        cursor=Depends(get_db_cursor)
):
    """
    Fetches Vulnerability Types and Contexts from Keep Secure 24 and
    synchronizes them with the local database tables using a Many-to-Many architecture.
    """
    try:
        # fetch data from kiss24
        map_type, map_context = sync_vuln_type_kiss24()

        #  sync context
        for ctx_id, ctx_name in map_context.items():
            cursor.execute("""
                INSERT INTO kiss24_context (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """, (ctx_id, ctx_name))

        if map_context:
            format_strings = ','.join(['%s'] * len(map_context))
            cursor.execute(f"DELETE FROM kiss24_context WHERE id NOT IN ({format_strings})", tuple(map_context.keys()))
        else:
            cursor.execute("DELETE FROM kiss24_context")

        #  sync vuln types
        for v_id, v_data in map_type.items():
            cursor.execute("""
                INSERT INTO kiss24_vuln_types (id, name)
                VALUES (%s, %s)
                ON CONFLICT (id) DO UPDATE SET name = EXCLUDED.name
            """, (v_id, v_data["name"]))

        if map_type:
            format_strings = ','.join(['%s'] * len(map_type))
            cursor.execute(f"DELETE FROM kiss24_vuln_types WHERE id NOT IN ({format_strings})", tuple(map_type.keys()))
        else:
            cursor.execute("DELETE FROM kiss24_vuln_types")

        # sync associations (Many-to-Many links)
        # Clear existing associations safely
        cursor.execute("DELETE FROM kiss24_vuln_context_association")

        # Build a list of tuples linking Vulns to Contexts
        association_values = []
        for v_id, v_data in map_type.items():
            for ctx in v_data.get("contexts", []):
                association_values.append((v_id, ctx["uuid"]))

        # Execute a batch insert for all associations
        if association_values:
            cursor.executemany("""
                INSERT INTO kiss24_vuln_context_association (vuln_id, context_id)
                VALUES (%s, %s)
                ON CONFLICT DO NOTHING
            """, association_values)

        # Commit all 3 table updates at once!
        cursor.connection.commit()

        # Log the audit event
        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="KISS24_VULN_TYPE_SYNC",
            resource_type="KISS24",
            resource_id="N/A",
            details=f"Synced {len(map_context)} Contexts, {len(map_type)} Vuln Types, and {len(association_values)} Connections."
        )

        return {
            "status": "Success",
            "message": "Many-to-Many Synchronization complete.",
            "contexts_synced": len(map_context),
            "vuln_types_synced": len(map_type),
            "associations_created": len(association_values)
        }

    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync KISS24 Vulnerability Types: {str(e)}"
        )


@router.post("/sync-user-kiss24-uuid", status_code=status.HTTP_200_OK, summary="[Admin Only]")
def sync_user_kiss24_uuid(
        current_user: dict = Depends(require_admin),
        cursor=Depends(get_db_cursor)
):
    """
    Fetch the active users' emails from the database and retrieve/update their kiss24 UUIDs.
    """
    try:
        # fetch active user emails
        email_list = []
        cursor.execute("""
            SELECT email FROM users WHERE end_week IS NULL and end_year IS NULL
        """)
        for row in cursor.fetchall():
            email_list.append(row[0])

        if not email_list:
            return {"message": "No active users found to sync.", "updated_count": 0}

        # get the mapping from kiss24
        sync_dat = map_mario_user_kiss24_uuid(email_list)

        if not sync_dat:
            return {"message": "No matching users found in Keep Secure 24.", "updated_count": 0}

        # update the database
        updated_count = 0
        for email, kiss_uuid in sync_dat.items():
            cursor.execute("""
                UPDATE users SET kiss24_uuid = %s WHERE email = %s
            """, (kiss_uuid, email))
            # rowcount tells us if a row was actually updated
            updated_count += cursor.rowcount

        # commit and log
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="KISS24_USER_UUID_SYNC",
            resource_type="USERS",
            resource_id="N/A",
            details=f"Synced {updated_count} users with their KISS24 UUIDs."
        )

        return {
            "status": "Success",
            "message": f"Successfully updated {updated_count} users.",
            "updated_count": updated_count,
            "mapped_emails": list(sync_dat.keys())
        }

    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync user UUIDs: {str(e)}"
        )


# Creation action
@router.post("/{test_id}/create-test", status_code=status.HTTP_200_OK)
# Creation action
@router.post("/{test_id}/create-test", status_code=status.HTTP_200_OK)
def create_kiss24_test(
        test_id: str,
        current_user: dict = Depends(get_current_user),
        cursor=Depends(get_db_cursor)
):
    """
    Creates a new test in Keep Secure 24 using the user's personal API Key.
    """
    try:
        # fetch & Decrypt User's Personal API Key
        cursor.execute("SELECT kiss24_api_key FROM users WHERE id = %s", (str(current_user["id"]),))
        key_row = cursor.fetchone()

        if not key_row or not key_row[0]:
            raise HTTPException(status_code=400,
                                detail="You must configure your personal Keep Secure 24 API key first.")

        cipher = get_cipher()
        try:
            user_api_key = cipher.decrypt(key_row[0].encode('utf-8')).decode('utf-8')
        except Exception:
            raise HTTPException(status_code=400,
                                detail="Failed to decrypt your personal API key. Please reset it in your profile.")

        # fetch required data for payload
        cursor.execute("""
            SELECT t.name, t.start_year, t.start_week, t.kiss24,
                   sl.name as service_lane_name,
                   c.kiss24_uuid as country_kiss24_uuid,
                   ra.kiss24_asset_id
            FROM tests t
            LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
            LEFT JOIN test_assets ta ON t.id = ta.test_id
            LEFT JOIN assets a ON ta.asset_id = a.id
            LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
            LEFT JOIN countries c ON ra.country_id = c.id
            WHERE t.id = %s LIMIT 1
        """, (test_id,))
        row = cursor.fetchone()

        if not row:
            raise HTTPException(status_code=404, detail="Test not found.")

        test_name, start_year, start_week, existing_kiss24, service_lane, country_uuid, asset_uuid = row

        # Block if already created or missing identifiers
        if existing_kiss24:
            raise HTTPException(status_code=400, detail="Test is already registered in Keep Secure 24.")
        if not country_uuid or not asset_uuid:
            raise HTTPException(status_code=400, detail="Missing Country UUID or Asset ID.")
        if not start_year or not start_week:
            raise HTTPException(status_code=400, detail="Test must be scheduled (Year and Week) before creation.")

        # Format Payload Data
        start_date = datetime.fromisocalendar(start_year, start_week, 1)
        start_date_str = start_date.strftime("%Y-%m-%d")

        full_test_name = f"{test_name} - {service_lane or 'Unknown Service'} {start_year}"

        payload = {
            "details": "to do",
            "scheduled_start": start_date_str,
            "auto_start": True,
            "private": False,
            "light": False,
            "assets": [str(asset_uuid)],
            "name": full_test_name
        }

        # Fire to kiss24 with user key
        new_test_uuid = create_test(str(country_uuid), payload, user_api_key)

        if not new_test_uuid:
            raise HTTPException(status_code=500,
                                detail="KISS24 API did not return a valid Test UUID. Ensure your API key has creation permissions.")

        cursor.execute("UPDATE tests SET kiss24 = %s WHERE id = %s", (new_test_uuid, test_id))
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user.get("role", "admin"),
            action="KISS24_TEST_CREATED",
            resource_type="KISS24",
            resource_id=str(test_id),
            details=f"Created Keep Secure 24 Test: {new_test_uuid}"
        )

        return {"status": "Success", "kiss24_uuid": new_test_uuid, "message": "Test successfully created in KISS24!"}

    except HTTPException:
        raise
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


# live fetching info
@router.get("/{test_id}/live-status", status_code=status.HTTP_200_OK)
def get_kiss24_live_status(
        test_id: str,
        current_user: dict = Depends(get_current_user),
        cursor=Depends(get_db_cursor)
):
    """
    Fetches the live status and details of a specific test from Keep Secure 24.
    """
    try:
        # 1. Get the KISS24 UUID for this test from our DB
        cursor.execute("SELECT kiss24 FROM tests WHERE id = %s", (test_id,))
        row = cursor.fetchone()

        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="This test is not yet linked to Keep Secure 24.")

        kiss24_uuid = str(row[0])

        # 2. Fetch from KISS24 API
        raw_data = get_test_info(kiss24_uuid)

        if not raw_data or not raw_data.get("items") or len(raw_data["items"]) == 0:
            raise HTTPException(status_code=404, detail="Test found in DB, but missing from KISS24 API.")

        # 3. Extract exactly what we need
        item = raw_data["items"][0]

        # Use (dict or {}) to safely chain .get() even if the parent object is None
        return {
            "id": item.get("id"),
            "name": item.get("name"),
            "state": item.get("state"),
            "light": item.get("light"),
            "scheduled_date": item.get("scheduled_date"),
            "organisation_name": (item.get("organisation") or {}).get("name"),
            "requested_at": item.get("requested_at"),
            "requested_by_email": (item.get("requested_by") or {}).get("email"),
            "started_at": item.get("started_at"),
            "started_by_email": (item.get("started_by") or {}).get("email"),
            "ended_at": item.get("ended_at"),
            "ended_by_email": (item.get("ended_by") or {}).get("email"),
        }

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))


@router.get("/{test_id}/vulnerabilities", status_code=status.HTTP_200_OK)
def get_kiss24_vulnerabilities(
        test_id: str,
        current_user: dict = Depends(get_current_user),
        cursor=Depends(get_db_cursor)
):
    """
    Fetches the published vulnerabilities for a specific test from Keep Secure 24.
    """
    try:
        # 1. Get the KISS24 UUID for this test from our DB
        cursor.execute("SELECT kiss24 FROM tests WHERE id = %s", (test_id,))
        row = cursor.fetchone()

        if not row or not row[0]:
            raise HTTPException(status_code=404, detail="This test is not yet linked to Keep Secure 24.")

        kiss24_uuid = str(row[0])

        # 2. Fetch from KISS24 API
        raw_data = get_test_vulns_info(kiss24_uuid)

        if not raw_data or not raw_data.get("items"):
            return []  # Return an empty array if there are no vulnerabilities yet

        # 3. Extract only the required fields
        vulns = []
        for item in raw_data["items"]:
            vulns.append({
                "uuid": item.get("uuid"),
                "id": item.get("id"),
                "description": item.get("description"),
                "state": item.get("state"),
                "severity": item.get("severity"),
                "published_at": item.get("published_at"),
                "published_by_name": (item.get("published_by") or {}).get("name")
            })

        return vulns

    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))