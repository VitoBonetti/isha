import json
from collections import defaultdict
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from sqlalchemy.dialects.postgresql import insert
from models.raw_assets import AssetCriteria, RawAssets, RawAssetsSnowMetadata, AssetTypes
from models.territories import Country
from models.assets import Assets
from models.tests import Tests, TestAssets, TestStages
from models.services import ServiceLanes
from audit_logger import log_audit_event
from utils.timeaware import aware_utcnow


def get_valid_fields():
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


def get_all_criteria(db: Session):
    criteria = db.query(AssetCriteria).order_by(AssetCriteria.year.desc()).all()
    return [
        {
            "id": str(c.id), "year": c.year, "criticality_threshold": c.criticality_threshold,
            "kpi_rules": c.kpi_rules, "updated_at": c.updated_at, "is_evaluated": c.is_evaluated
        }
        for c in criteria
    ]


def upsert_criteria(db: Session, payload, current_user: dict):
    rules_json = [rule.dict() for rule in payload.kpi_rules]

    # SQLAlchemy PostgreSQL specific ON CONFLICT DO UPDATE
    stmt = insert(AssetCriteria).values(
        year=payload.year,
        criticality_threshold=payload.criticality_threshold,
        kpi_rules=rules_json,
        updated_at=aware_utcnow(),
        is_evaluated=False
    )

    stmt = stmt.on_conflict_do_update(
        index_elements=['year'],
        set_={
            'criticality_threshold': stmt.excluded.criticality_threshold,
            'kpi_rules': stmt.excluded.kpi_rules,
            'updated_at': aware_utcnow(),
            'is_evaluated': False
        }
    ).returning(AssetCriteria.id)

    new_id = db.execute(stmt).scalar()
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="CRITERIA_UPSERTED",
        resource_type="ASSET_CRITERIA", resource_id=str(new_id),
        details=f"Asset criteria configured for year {payload.year}."
    )
    return {"message": "Criteria saved successfully.", "id": str(new_id)}


def delete_criteria(db: Session, year: int):
    db.query(AssetCriteria).filter(AssetCriteria.year == year).delete()
    db.commit()
    return {"message": f"Criteria for {year} deleted."}


def evaluate_assets(db: Session, year: int, req, current_user: dict):
    criteria = db.query(AssetCriteria).filter(AssetCriteria.year == year).first()
    if not criteria:
        raise HTTPException(status_code=404, detail=f"No criteria rules found for {year}.")

    threshold = criteria.criticality_threshold
    kpi_rules = criteria.kpi_rules

    query = (db.query(RawAssets, RawAssetsSnowMetadata.snow_data)
    .outerjoin(Country, RawAssets.country_id == Country.id)
    .outerjoin(RawAssetsSnowMetadata, RawAssets.id == RawAssetsSnowMetadata.correlation_id)
    .filter(
        or_(Country.is_team == False, Country.is_team.is_(None)),
        RawAssets.snow_number.isnot(None),
        RawAssets.snow_active == True
    ))

    if req.raw_asset_ids:
        query = query.filter(RawAssets.id.in_(req.raw_asset_ids))

    assets = query.all()
    updates_made = 0
    rules_by_field = defaultdict(list)

    if kpi_rules:
        for rule in kpi_rules:
            rules_by_field[rule.get('field')].append(rule)

    for raw_asset_obj, snow_data in assets:
        new_is_kpi = True if kpi_rules else False
        snow_payload = snow_data or {}

        for field_name, rules in rules_by_field.items():
            has_positive_rules = False
            passed_positive = False
            passed_negative = True

            for rule in rules:
                operator = rule.get('operator')
                rule_value = rule.get('value')

                if field_name.startswith('snow:'):
                    snow_key = field_name.split('snow:')[1]
                    asset_value = snow_payload.get(snow_key)
                else:
                    # Safely pull the attribute from the SQLAlchemy Model
                    asset_value = getattr(raw_asset_obj, field_name, None)

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
                biz_critical_val = int(raw_asset_obj.business_critical or 0)
            except (ValueError, TypeError):
                biz_critical_val = 0
            new_is_critical = biz_critical_val >= threshold

        if raw_asset_obj.is_critical != new_is_critical or raw_asset_obj.is_kpi != new_is_kpi:
            raw_asset_obj.is_critical = new_is_critical
            raw_asset_obj.is_kpi = new_is_kpi
            updates_made += 1

    # Update Criteria Evaluation Status
    criteria.updated_at = aware_utcnow()
    criteria.is_evaluated = True
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="CRITERIA_EVALUATED",
        resource_type="ASSET_CRITERIA", resource_id=str(year),
        details=f"Evaluated {len(assets)} assets against {year} criteria. Updated {updates_made} records."
    )

    return {"message": "Evaluation complete.", "assets_evaluated": len(assets), "assets_updated": updates_made}


def dashboard_data(db: Session):
    query = (db.query(
        Tests.name.label("Name"),
        ServiceLanes.name.label("Service"),
        RawAssets.id.label("Inventory_Id"),
        RawAssets.snow_number.label("ID"),
        Country.code,
        AssetTypes.name.label("Type"),
        RawAssets.snow_active.label("Status"),
        RawAssets.business_critical,
        RawAssets.confidentiality_rating,
        RawAssets.integrity_rating,
        RawAssets.availability_rating,
        RawAssets.facing_internet,
        Tests.start_week,
        Tests.start_year,
        Tests.stages,
        RawAssets.is_kpi,
        RawAssets.is_critical
    ).select_from(Tests)
    .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
    .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
    .outerjoin(Assets, TestAssets.asset_id == Assets.id)
    .outerjoin(RawAssets, Assets.raw_asset_id == RawAssets.id)
    .outerjoin(AssetTypes, RawAssets.asset_type_id == AssetTypes.id)
    .outerjoin(Country, RawAssets.country_id == Country.id)
    .filter(
        or_(Country.is_team == False, Country.is_team.is_(None)),
        ServiceLanes.auto_provision_workspace == True,
        RawAssets.is_kpi == True,
        Tests.stages != TestStages.STOPPED
    ))

    total_count = query.count()
    rows = query.all()

    items = [
        {
            "Name": r.Name,
            "Service": r.Service,
            "Inventory_Id": str(r.Inventory_Id) if r.Inventory_Id else None,
            "ID": r.ID,
            "code": r.code,
            "Type": r.Type,
            "Status": r.Status,
            "business_critical": r.business_critical,
            "confidentiality_rating": r.confidentiality_rating,
            "integrity_rating": r.integrity_rating,
            "availability_rating": r.availability_rating,
            "facing_internet": r.facing_internet,
            "start_week": r.start_week,
            "start_year": r.start_year,
            "stages": r.stages.name if r.stages else None,
            "is_kpi": r.is_kpi,
            "is_critical": r.is_critical
        }
        for r in rows
    ]

    return {"items": items, "total_count": total_count}