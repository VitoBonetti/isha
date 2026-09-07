import uuid
import json
from typing import List
from collections import defaultdict
from fastapi import APIRouter, Depends, HTTPException
from database import get_db_cursor
from routers.auth import require_admin, require_admin_or_read_only
from schema import AssetCriteriaBase, AssetCriteriaResponse, EvaluateCriteriaRequest
from audit_logger import log_audit_event

router = APIRouter(prefix="/api/asset-criteria", tags=["Asset Criteria Engine"])


@router.get("/fields", summary="Get valid asset criteria fields and their relation endpoints")
def get_valid_fields(current_user: dict = Depends(require_admin_or_read_only)):
    """Returns the schema dictionary so the frontend can dynamically build the UI."""
    return [
        {"name": "business_critical", "label": "Business Critical (1-10)", "type": "number"},
        {"name": "confidentiality_rating", "label": "Confidentiality Rating", "type": "number"},
        {"name": "integrity_rating", "label": "Integrity Rating", "type": "number"},
        {"name": "availability_rating", "label": "Availability Rating", "type": "number"},
        {"name": "facing_internet", "label": "Internet Facing (Yes/No/Unknown)", "type": "string"},
        {"name": "snow:application_type", "label": "Application Type (ServiceNow)", "type": "string"},
        {"name": "asset_type_id", "label": "Asset Type", "type": "relation", "endpoint": "/api/assets/types"},
        {"name": "country_id", "label": "Country", "type": "relation", "endpoint": "/api/countries/"},
        {"name": "service_forecast_id", "label": "Service Lane", "type": "relation", "endpoint": "/api/services/"},
        {"name": "category_id", "label": "Category", "type": "relation", "endpoint": "/api/board/categories/"}
    ]


def evaluate_kpi_rule(asset_value, operator: str, rule_value):
    """Safely evaluates a dynamic rule, explicitly supporting null/None values and empty strings."""

    if asset_value == "":
        asset_value = None

    if isinstance(asset_value, bool):
        asset_value = str(asset_value).lower()

    if operator == 'is_null': return asset_value is None
    if operator == 'is_not_null': return asset_value is not None

    if asset_value is None:
        if operator == '==': return rule_value is None
        if operator == '!=': return rule_value is not None
        return False

    if rule_value is None:
        if operator == '==': return False
        if operator == '!=': return True
        return False

    if operator == '==': return str(asset_value).lower() == str(rule_value).lower()
    if operator == '!=': return str(asset_value).lower() != str(rule_value).lower()

    if operator == 'in':
        if isinstance(rule_value, list):
            return str(asset_value).lower() in [str(v).lower() for v in rule_value]
        return False

    if operator == 'not_in':
        if isinstance(rule_value, list):
            return str(asset_value).lower() not in [str(v).lower() for v in rule_value]
        return True

    if operator == 'contains': return str(rule_value).lower() in str(asset_value).lower()

    if operator == '>':
        try:
            return float(asset_value) > float(rule_value)
        except (ValueError, TypeError):
            return False

    if operator == '<':
        try:
            return float(asset_value) < float(rule_value)
        except (ValueError, TypeError):
            return False

    return False


@router.get("/", summary="List all asset criteria configurations")
def get_all_criteria(current_user: dict = Depends(require_admin_or_read_only), cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT id, year, criticality_threshold, kpi_rules, updated_at, is_evaluated FROM asset_criteria ORDER BY year DESC")
    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/", summary="Create or update asset criteria for a year")
def upsert_criteria(payload: AssetCriteriaBase, current_user: dict = Depends(require_admin),
                    cursor=Depends(get_db_cursor)):
    rules_json = json.dumps([rule.dict() for rule in payload.kpi_rules])

    # If the rules are updated, we set is_evaluated to FALSE because they need to be re-run!
    cursor.execute("""
        INSERT INTO asset_criteria (id, year, criticality_threshold, kpi_rules, updated_at, is_evaluated)
        VALUES (gen_random_uuid(), %s, %s, %s, CURRENT_TIMESTAMP, FALSE)
        ON CONFLICT (year) DO UPDATE SET 
            criticality_threshold = EXCLUDED.criticality_threshold,
            kpi_rules = EXCLUDED.kpi_rules,
            updated_at = CURRENT_TIMESTAMP,
            is_evaluated = FALSE
        RETURNING id
    """, (payload.year, payload.criticality_threshold, rules_json))

    new_id = cursor.fetchone()[0]
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="CRITERIA_UPSERTED",
        resource_type="ASSET_CRITERIA", resource_id=str(new_id),
        details=f"Asset criteria configured for year {payload.year}."
    )
    return {"message": "Criteria saved successfully.", "id": str(new_id)}


@router.delete("/{year}", summary="Delete criteria for a year")
def delete_criteria(year: int, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM asset_criteria WHERE year = %s", (year,))
    cursor.connection.commit()
    return {"message": f"Criteria for {year} deleted."}


@router.post("/evaluate/{year}", summary="Execute evaluation engine on raw_assets")
def evaluate_assets(year: int, req: EvaluateCriteriaRequest, current_user: dict = Depends(require_admin),
                    cursor=Depends(get_db_cursor)):
    cursor.execute("SELECT criticality_threshold, kpi_rules FROM asset_criteria WHERE year = %s", (year,))
    criteria_row = cursor.fetchone()
    if not criteria_row:
        raise HTTPException(status_code=404, detail=f"No criteria rules found for {year}.")

    threshold, kpi_rules = criteria_row

    query = """
        SELECT ra.*, sm.snow_data
        FROM raw_assets ra
        LEFT JOIN countries c ON ra.country_id = c.id
        LEFT JOIN raw_assets_snow_metadata sm ON ra.id = sm.correlation_id
        WHERE (c.is_team = FALSE OR c.is_team IS NULL) AND ra.snow_number IS NOT NULL and ra.snow_active = TRUE
    """
    params = []
    if req.raw_asset_ids:
        format_strings = ','.join(['%s'] * len(req.raw_asset_ids))
        query += f" AND ra.id IN ({format_strings})"
        params.extend([str(aid) for aid in req.raw_asset_ids])

    cursor.execute(query, tuple(params))
    assets = cursor.fetchall()
    columns = [col[0] for col in cursor.description]

    updates_made = 0
    rules_by_field = defaultdict(list)
    if kpi_rules:
        for rule in kpi_rules:
            rules_by_field[rule.get('field')].append(rule)

    for asset_row in assets:
        asset = dict(zip(columns, asset_row))
        asset_id = asset['id']

        new_is_kpi = True if kpi_rules else False

        for field_name, rules in rules_by_field.items():
            has_positive_rules = False
            passed_positive = False
            passed_negative = True

            for rule in rules:
                operator = rule.get('operator')
                rule_value = rule.get('value')

                if field_name.startswith('snow:'):
                    snow_key = field_name.split('snow:')[1]
                    snow_payload = asset.get('snow_data') or {}
                    asset_value = snow_payload.get(snow_key)
                else:
                    asset_value = asset.get(field_name)

                rule_passed = evaluate_kpi_rule(asset_value, operator, rule_value)

                if operator in ['!=', 'not_in']:
                    if not rule_passed:
                        passed_negative = False
                else:
                    has_positive_rules = True
                    if rule_passed:
                        passed_positive = True

            if has_positive_rules:
                field_passed = passed_positive and passed_negative
            else:
                field_passed = passed_negative

            if not field_passed:
                new_is_kpi = False
                break

        new_is_critical = False
        if new_is_kpi:
            try:
                biz_critical_val = int(asset.get('business_critical') or 0)
            except (ValueError, TypeError):
                biz_critical_val = 0
            new_is_critical = biz_critical_val >= threshold

        if asset.get('is_critical') != new_is_critical or asset.get('is_kpi') != new_is_kpi:
            cursor.execute("UPDATE raw_assets SET is_critical = %s, is_kpi = %s WHERE id = %s",
                           (new_is_critical, new_is_kpi, str(asset_id)))
            updates_made += 1

    # 4. Stamp the evaluation time AND set the boolean flag
    cursor.execute("UPDATE asset_criteria SET updated_at = CURRENT_TIMESTAMP, is_evaluated = TRUE WHERE year = %s", (year,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="CRITERIA_EVALUATED",
        resource_type="ASSET_CRITERIA", resource_id=str(year),
        details=f"Evaluated {len(assets)} assets against {year} criteria. Updated {updates_made} records."
    )

    return {"message": "Evaluation complete.", "assets_evaluated": len(assets), "assets_updated": updates_made}


@router.get('/dashboard-data', summary='Dashboard data. only temp endpoint')
def dashboard_data(current_user: dict = Depends(require_admin_or_read_only),
                    cursor=Depends(get_db_cursor)):
    cursor.execute("""
    SELECT COUNT(*) FROM tests t
    LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
    LEFT JOIN test_assets ta ON t.id = ta.test_id
    LEFT JOIN assets a ON ta.asset_id = a.id
    LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
    LEFT JOIN asset_types at ON ra.asset_type_id = at.id
    LEFT JOIN countries c ON ra.country_id = c.id
    WHERE (c.is_team = FALSE OR c.is_team IS NULL) AND sl.auto_provision_workspace = TRUE AND ra.is_kpi = TRUE 
    AND t.stages != 'STOPPED'
    """)
    total_count = cursor.fetchone()[0]

    cursor.execute("""
    SELECT t.name as Name, sl.name as Service, ra.id as Inventory_Id, ra.snow_number as ID, c.code, at.name as Type, 
    ra.snow_active as Status, ra.business_critical, ra.confidentiality_rating, ra.integrity_rating, 
    ra.availability_rating, ra.facing_internet, t.start_week, t.start_year, t.stages, ra.is_kpi, ra.is_critical 
    FROM tests t
    LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
    LEFT JOIN test_assets ta ON t.id = ta.test_id
    LEFT JOIN assets a ON ta.asset_id = a.id
    LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
    LEFT JOIN asset_types at ON ra.asset_type_id = at.id
    LEFT JOIN countries c ON ra.country_id = c.id
    WHERE (c.is_team = FALSE OR c.is_team IS NULL) AND sl.auto_provision_workspace = TRUE AND ra.is_kpi = TRUE 
    AND t.stages != 'STOPPED'
    """)
    columns = [col[0] for col in cursor.description]

    items = [dict(zip(columns, row)) for row in cursor.fetchall()]
    return {"items": items, "total_count": total_count}