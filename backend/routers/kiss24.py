from fastapi import APIRouter, Depends, HTTPException, status
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
from audit_logger import log_audit_event
from sqlalchemy.testing.pickleable import User
from utils.timeaware import aware_utcnow
from utils.kiss24_service import map_asset_onetrust_custom_field, map_organizations

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
    1. Fetches OneTrust ID -> KISS24 Asset UUID mappings from KISS24.
    2. Matches with raw_assets_snow_metadata.snow_data->>'u_onetrust_number'.
    3. Updates raw_assets.kiss24_asset_id for all matches.
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