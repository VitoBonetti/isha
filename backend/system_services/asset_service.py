import uuid
import pandas as pd
import io
from fastapi import HTTPException
from starlette import status
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, literal_column

# Import SQLAlchemy Models
from models.assets import Assets
from models.raw_assets import AssetTypes, RawAssets, RawAssetsSnowMetadata
from models.histories import AssetHistory, TestHistory
from models.territories import Country
from models.services import ServiceLanes, ServiceCategories
from models.tests import Tests, TestAssets, Assignments, TestStages
from models.users import Users

from audit_logger import log_audit_event
from utils.snow_sync import process_and_sync_snow_data, fetch_raw_snow_data
from utils.timeaware import aware_utcnow
from database import SessionLocal
from routers.auth import verify_lane_access
from schema import AssetTypeBase, RawAssetCreate, BulkAssetRequest, BulkServiceUpdateRequest

MAX_FILE_SIZE = 5 * 1024 * 1024  # 5 MB limit
ALLOWED_MIME_TYPES = {
    "text/csv",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
}


###################################
# ---  VALIDATIONS HELPERS    --- #
###################################
def is_valid_file_signature(contents: bytes, filename: str) -> bool:
    if not contents:
        return False
    ext = filename.lower().split('.')[-1]
    if ext == 'xlsx':
        return contents.startswith(b'\x50\x4B\x03\x04')
    elif ext == 'xls':
        return contents.startswith(b'\xD0\xCF\x11\xE0\xA1\xB1\x1A\xE1')
    elif ext == 'csv':
        return b'\x00' not in contents[:1024]
    return False


def sanitize_csv_injection(text: str) -> str:
    if not text:
        return text
    if text.startswith(('=', '+', '-', '@')):
        return f"'{text}"
    return text


def insert_asset_history(db: Session, raw_asset_id: str, user_id: str, action: str, details: str):
    history_entry = AssetHistory(
        raw_asset_id=str(raw_asset_id),
        user_id=str(user_id) if user_id else None,
        action=action,
        details=details
    )
    db.add(history_entry)


###################################
# ---      ASSET TYPES        --- #
###################################
def get_all_asset_types(db: Session):
    return db.query(AssetTypes).order_by(AssetTypes.name.asc()).all()


def create_asset_type(db: Session, at: AssetTypeBase, current_user: dict):
    try:
        new_asset_type = AssetTypes(name=at.name)
        db.add(new_asset_type)
        db.commit()
        db.refresh(new_asset_type)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="ASSET_TYPE_CREATE",
            resource_type="ASSETS",
            resource_id=str(new_asset_type.id),
            details=f"Asset Type {new_asset_type.name} created with ID: {new_asset_type.id}"
        )
        return {"id": str(new_asset_type.id), "message": "Asset Type created."}
    except Exception:
        db.rollback()
        raise HTTPException(status_code=400, detail="Asset type name might already exist.")


def update_asset_type(db: Session, type_id: str, at: AssetTypeBase, current_user: dict):
    asset_type = db.query(AssetTypes).filter(AssetTypes.id == type_id).first()
    if not asset_type:
        raise HTTPException(status_code=404, detail="Asset type not found")

    asset_type.name = at.name
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="ASSET_TYPE_UPDATE",
        resource_type="ASSETS",
        resource_id=str(type_id),
        details=f"Asset Type {type_id} has been updated as {asset_type.name}"
    )
    return {"message": "Asset Type updated."}


def delete_asset_type(db: Session, type_id: str, current_user: dict):
    asset_type = db.query(AssetTypes).filter(AssetTypes.id == type_id).first()
    if not asset_type:
        raise HTTPException(status_code=404, detail="Asset type not found")

    db.delete(asset_type)
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="ASSET_TYPE_DELETED",
        resource_type="ASSETS",
        resource_id=str(type_id),
        details=f"Asset Type {type_id} has been Deleted"
    )
    return {"message": "Asset Type deleted."}


###################################
# ---      RAW ASSETS         --- #
###################################
def get_paginated_raw_assets(
    db: Session, page: int, limit: int, search: str, country_id: str,
    service_id: str, category_id: str, asset_type_id: str, facing_internet: str,
    business_critical: int, status: str, is_kpi: bool, is_critical: bool,
    sort_by: str, sort_dir: str
):
    offset = (page - 1) * limit

    query = db.query(
        RawAssets.id,
        RawAssets.name,
        Country.code.label("country_code"),
        Country.name.label("country_name"),
        ServiceLanes.name.label("service_name"),
        ServiceCategories.name.label("category_name"),
        AssetTypes.name.label("asset_type_name"),
        RawAssets.facing_internet,
        RawAssets.business_critical,
        RawAssets.snow_active,
        case((Assets.id.isnot(None), True), else_=False).label("is_promoted")
    ).outerjoin(Country, RawAssets.country_id == Country.id)\
     .outerjoin(ServiceLanes, RawAssets.service_forecast_id == ServiceLanes.id)\
     .outerjoin(ServiceCategories, RawAssets.category_id == ServiceCategories.id)\
     .outerjoin(AssetTypes, RawAssets.asset_type_id == AssetTypes.id)\
     .outerjoin(Assets, RawAssets.id == Assets.raw_asset_id)

    # Dynamic Filter Conditions
    if search:
        query = query.filter(RawAssets.name.ilike(f"%{search}%"))
    if country_id:
        query = query.filter(RawAssets.country_id == country_id)
    if service_id:
        query = query.filter(RawAssets.service_forecast_id == service_id)
    if category_id:
        query = query.filter(RawAssets.category_id == category_id)
    if asset_type_id:
        query = query.filter(RawAssets.asset_type_id == asset_type_id)
    if facing_internet == 'true':
        query = query.filter(RawAssets.facing_internet == True)
    elif facing_internet == 'false':
        query = query.filter(RawAssets.facing_internet == False)
    elif facing_internet == 'null':
        query = query.filter(RawAssets.facing_internet.is_(None))
    if business_critical is not None:
        query = query.filter(RawAssets.business_critical >= business_critical)
    if is_kpi is not None:
        query = query.filter(RawAssets.is_kpi == is_kpi)
    if is_critical is not None:
        query = query.filter(RawAssets.is_critical == is_critical)
    if status == 'raw':
        query = query.filter(Assets.id.is_(None))
    elif status == 'pool':
        query = query.filter(Assets.id.isnot(None))

    total_count = query.count()

    # Dynamic Sorting
    sort_map = {
        "name": RawAssets.name,
        "country": Country.code,
        "service": ServiceLanes.name,
        "category": ServiceCategories.name,
        "type": AssetTypes.name,
        "status": case((Assets.id.isnot(None), True), else_=False)
    }
    order_col = sort_map.get(sort_by, RawAssets.name)
    order_col = order_col.desc() if sort_dir.lower() == "desc" else order_col.asc()

    rows = query.order_by(order_col).offset(offset).limit(limit).all()

    items = [
        {
            "id": str(r[0]),
            "name": r[1],
            "country_code": r[2],
            "country_name": r[3],
            "service_name": r[4],
            "category_name": r[5],
            "asset_type_name": r[6],
            "facing_internet": r[7],
            "business_critical": r[8],
            "snow_active": r[9],
            "is_promoted": r[10]
        }
        for r in rows
    ]

    return {"items": items, "total_count": total_count}


def create_manual_raw_asset(db: Session, asset: RawAssetCreate, current_user: dict):
    c_id = str(asset.country_id) if asset.country_id else None
    s_id = str(asset.service_forecast_id) if asset.service_forecast_id else None
    cat_id = str(asset.category_id) if asset.category_id else None
    at_id = str(asset.asset_type_id)

    new_raw_asset = RawAssets(
        name=asset.name,
        description=asset.description,
        business_critical=asset.business_critical,
        confidentiality_rating=asset.confidentiality_rating,
        integrity_rating=asset.integrity_rating,
        availability_rating=asset.availability_rating,
        country_id=c_id,
        service_forecast_id=s_id,
        category_id=cat_id,
        asset_type_id=at_id,
        facing_internet=asset.facing_internet,
        duplicate_allowed=asset.duplicate_allowed,
        is_kpi=asset.is_kpi,
        is_critical=asset.is_critical
    )
    db.add(new_raw_asset)
    db.flush()

    new_id_str = str(new_raw_asset.id)

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="RAW_ASSET_CREATED",
        resource_type="RAW_ASSETS",
        resource_id=new_id_str,
        details=f"Asset {asset.name} has been created."
    )
    insert_asset_history(db, new_id_str, str(current_user["id"]), "CREATED", "Asset manually added to the system.")
    db.commit()

    return {"message": "Raw Asset created", "id": new_id_str}


def get_single_raw_asset(db: Session, raw_id: str, current_user: dict):
    query = db.query(
        RawAssets,
        case((Assets.id.isnot(None), True), else_=False).label("is_promoted"),
        Assets.is_archived,
        Assets.archived_years,
        RawAssetsSnowMetadata.snow_data
    ).outerjoin(Assets, RawAssets.id == Assets.raw_asset_id)\
     .outerjoin(RawAssetsSnowMetadata, RawAssets.id == RawAssetsSnowMetadata.correlation_id)\
     .filter(RawAssets.id == raw_id)

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        if lane_id:
            query = query.filter(RawAssets.service_forecast_id == str(lane_id))
        else:
            query = query.filter(RawAssets.service_forecast_id == '00000000-0000-0000-0000-000000000000')

    result = query.first()
    if not result:
        raise HTTPException(status_code=404, detail="Asset not found")

    r_asset, is_promoted, is_archived, archived_years, snow_data = result

    asset_data = {
        "id": str(r_asset.id),
        "name": r_asset.name,
        "description": r_asset.description,
        "business_critical": r_asset.business_critical,
        "confidentiality_rating": r_asset.confidentiality_rating,
        "integrity_rating": r_asset.integrity_rating,
        "availability_rating": r_asset.availability_rating,
        "country_id": str(r_asset.country_id) if r_asset.country_id else None,
        "service_forecast_id": str(r_asset.service_forecast_id) if r_asset.service_forecast_id else None,
        "category_id": str(r_asset.category_id) if r_asset.category_id else None,
        "asset_type_id": str(r_asset.asset_type_id) if r_asset.asset_type_id else None,
        "facing_internet": r_asset.facing_internet,
        "duplicate_allowed": r_asset.duplicate_allowed,
        "create_date": r_asset.create_date,
        "update_date": r_asset.update_date,
        "snow_number": r_asset.snow_number,
        "team_note": r_asset.team_note,
        "kiss24_asset_id": r_asset.kiss24_asset_id,
        "is_kpi": r_asset.is_kpi,
        "is_critical": r_asset.is_critical,
        "snow_active": r_asset.snow_active,
        "snow_data": snow_data,
        "is_promoted": is_promoted,
        "is_archived": is_archived,
        "archived_years": archived_years
    }

    # Asset History
    hist_rows = db.query(
        AssetHistory.id,
        AssetHistory.action,
        AssetHistory.details,
        AssetHistory.timestamp,
        Users.name.label("user_name")
    ).outerjoin(Users, AssetHistory.user_id == Users.id)\
     .filter(AssetHistory.raw_asset_id == raw_id)\
     .order_by(AssetHistory.timestamp.desc()).all()

    asset_data["history"] = [
        {
            "id": str(h[0]),
            "action": h[1],
            "details": h[2],
            "timestamp": h[3],
            "user_name": h[4]
        }
        for h in hist_rows
    ]

    # Completed Tests
    pentesters_sub = db.query(
        func.string_agg(func.distinct(Users.name), ', ')
    ).select_from(Assignments).join(Users, Assignments.user_id == Users.id)\
     .filter(Assignments.test_id == Tests.id).correlate(Tests).scalar_subquery()

    completion_sub = db.query(TestHistory.timestamp)\
     .filter(TestHistory.test_id == Tests.id, TestHistory.action == 'COMPLETED')\
     .order_by(TestHistory.timestamp.desc()).limit(1).correlate(Tests).scalar_subquery()

    test_rows = db.query(
        Tests.id,
        Tests.name,
        Tests.start_week,
        Tests.start_year,
        ServiceLanes.name.label("service_lane"),
        pentesters_sub.label("pentesters"),
        completion_sub.label("completion_date")
    ).join(TestAssets, Tests.id == TestAssets.test_id)\
     .join(Assets, TestAssets.asset_id == Assets.id)\
     .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)\
     .filter(Assets.raw_asset_id == raw_id, Tests.stages == TestStages.COMPLETED)\
     .order_by(completion_sub.desc().nullslast()).all()

    asset_data["completed_tests"] = [
        {
            "id": str(t[0]),
            "name": t[1],
            "start_week": t[2],
            "start_year": t[3],
            "service_lane": t[4],
            "pentesters": t[5],
            "completion_date": t[6]
        }
        for t in test_rows
    ]

    return asset_data


def update_raw_asset(db: Session, raw_id: str, asset: RawAssetCreate, current_user: dict):
    r_asset = db.query(RawAssets).filter(RawAssets.id == raw_id).first()
    if not r_asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    verify_lane_access(current_user, str(r_asset.service_forecast_id))

    old_name = r_asset.name
    old_internet = r_asset.facing_internet
    old_duplicate_allowed = r_asset.duplicate_allowed
    old_country = r_asset.countries.name if r_asset.countries else "None"
    old_service = r_asset.services_lanes.name if r_asset.services_lanes else "None"
    old_category = r_asset.service_categories.name if r_asset.service_categories else "None"
    old_type = r_asset.asset_types.name if r_asset.asset_types else "None"
    old_team_note = r_asset.team_note
    old_kiss24_asset_id = r_asset.kiss24_asset_id

    changes = []

    if current_user.get('role') == 'maintainer':
        r_asset.team_note = asset.team_note
        r_asset.kiss24_asset_id = asset.kiss24_asset_id
        r_asset.update_date = aware_utcnow()

        if old_team_note != asset.team_note:
            changes.append("Team Note was updated")
        if old_kiss24_asset_id != asset.kiss24_asset_id:
            changes.append("Kiss 24 asset uuid was updated")
    else:
        c_id = str(asset.country_id) if asset.country_id else None
        s_id = str(asset.service_forecast_id) if asset.service_forecast_id else None
        cat_id = str(asset.category_id) if asset.category_id else None
        at_id = str(asset.asset_type_id) if asset.asset_type_id else None

        new_country_obj = db.query(Country).filter(Country.id == c_id).first() if c_id else None
        new_service_obj = db.query(ServiceLanes).filter(ServiceLanes.id == s_id).first() if s_id else None
        new_category_obj = db.query(ServiceCategories).filter(ServiceCategories.id == cat_id).first() if cat_id else None
        new_type_obj = db.query(AssetTypes).filter(AssetTypes.id == at_id).first() if at_id else None

        new_country = new_country_obj.name if new_country_obj else "None"
        new_service = new_service_obj.name if new_service_obj else "None"
        new_category = new_category_obj.name if new_category_obj else "None"
        new_type = new_type_obj.name if new_type_obj else "None"

        r_asset.name = asset.name
        r_asset.description = asset.description
        r_asset.business_critical = asset.business_critical
        r_asset.confidentiality_rating = asset.confidentiality_rating
        r_asset.integrity_rating = asset.integrity_rating
        r_asset.availability_rating = asset.availability_rating
        r_asset.country_id = c_id
        r_asset.service_forecast_id = s_id
        r_asset.category_id = cat_id
        r_asset.asset_type_id = at_id
        r_asset.facing_internet = asset.facing_internet
        r_asset.duplicate_allowed = asset.duplicate_allowed
        r_asset.snow_number = asset.snow_number
        r_asset.team_note = asset.team_note
        r_asset.kiss24_asset_id = asset.kiss24_asset_id
        r_asset.is_kpi = asset.is_kpi
        r_asset.is_critical = asset.is_critical
        r_asset.snow_active = asset.snow_active
        r_asset.update_date = aware_utcnow()

        if old_name != asset.name: changes.append(f"Name: '{old_name}' ➔ '{asset.name}'")
        if old_type != new_type: changes.append(f"Type: '{old_type}' ➔ '{new_type}'")
        if old_country != new_country: changes.append(f"Country: '{old_country}' ➔ '{new_country}'")
        if old_service != new_service: changes.append(f"Service: '{old_service}' ➔ '{new_service}'")
        if old_category != new_category: changes.append(f"Category: '{old_category}' ➔ '{new_category}'")
        if old_internet != asset.facing_internet: changes.append(f"Internet Facing: {old_internet} ➔ {asset.facing_internet}")
        if old_duplicate_allowed != asset.duplicate_allowed: changes.append(f"Allow Duplicates: {old_duplicate_allowed} ➔ {asset.duplicate_allowed}")

    details_str = " | ".join(changes) if changes else "Description Updated."
    insert_asset_history(db, raw_id, str(current_user["id"]), "UPDATED", details_str)

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_UPDATED",
        resource_type="RAW_ASSETS", resource_id=str(raw_id),
        details=f"Asset {asset.name} has been updated. ID: {raw_id}"
    )
    db.commit()
    return {"message": "Raw Asset updated"}


def delete_raw_asset(db: Session, raw_id: str, year: int, current_user: dict):
    completed_count = db.query(func.count(Tests.id))\
        .select_from(TestAssets)\
        .join(Tests, TestAssets.test_id == Tests.id)\
        .join(Assets, TestAssets.asset_id == Assets.id)\
        .filter(Assets.raw_asset_id == raw_id, Tests.stages == TestStages.COMPLETED).scalar() or 0

    if completed_count > 0:
        pool_asset = db.query(Assets).filter(Assets.raw_asset_id == raw_id).first()
        current_years = list(pool_asset.archived_years) if (pool_asset and pool_asset.archived_years) else []
        if year not in current_years:
            current_years.append(year)

        if pool_asset:
            pool_asset.archived_years = current_years
            pool_asset.is_archived = True

        insert_asset_history(db, str(raw_id), str(current_user["id"]), "ARCHIVED", f"Asset safely archived in {year}.")
        action_msg = f"Asset safely archived to preserve {completed_count} completed tests."
        log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_ARCHIVED",
                        resource_type="RAW_ASSETS", resource_id=str(raw_id), details=f"Asset archived for {year}.")
    else:
        raw_asset = db.query(RawAssets).filter(RawAssets.id == raw_id).first()
        if raw_asset:
            db.delete(raw_asset)
        action_msg = "Asset permanently deleted."
        log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_DELETED",
                        resource_type="RAW_ASSETS", resource_id=str(raw_id), details="Asset deleted.")

    db.commit()
    return {"message": action_msg}


def restore_raw_asset(db: Session, raw_id: str, year: int, current_user: dict):
    pool_asset = db.query(Assets).filter(Assets.raw_asset_id == raw_id).first()
    if not pool_asset:
        raise HTTPException(status_code=404, detail="Active pool asset not found.")

    current_years = list(pool_asset.archived_years) if pool_asset.archived_years else []
    if year in current_years:
        current_years.remove(year)

    pool_asset.archived_years = current_years
    pool_asset.is_archived = False

    insert_asset_history(db, str(raw_id), str(current_user["id"]), "RESTORED", f"Asset restored to the active pool for {year}.")
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_RESTORED",
                    resource_type="RAW_ASSETS", resource_id=str(raw_id), details=f"Asset restored for {year}.")

    db.commit()
    return {"message": f"Asset successfully restored for {year}!"}


def bulk_delete_raw_assets(db: Session, req: BulkAssetRequest, year: int, current_user: dict):
    deleted_count = 0
    archived_count = 0
    for raw_id in req.raw_asset_ids:
        completed_count = db.query(func.count(Tests.id))\
            .select_from(TestAssets)\
            .join(Tests, TestAssets.test_id == Tests.id)\
            .join(Assets, TestAssets.asset_id == Assets.id)\
            .filter(Assets.raw_asset_id == str(raw_id), Tests.stages == TestStages.COMPLETED).scalar() or 0

        if completed_count > 0:
            pool_asset = db.query(Assets).filter(Assets.raw_asset_id == str(raw_id)).first()
            current_years = list(pool_asset.archived_years) if (pool_asset and pool_asset.archived_years) else []
            if year not in current_years:
                current_years.append(year)

            if pool_asset:
                pool_asset.archived_years = current_years
                pool_asset.is_archived = True

            insert_asset_history(db, str(raw_id), str(current_user["id"]), "ARCHIVED", f"Asset safely archived in {year}.")
            archived_count += 1
        else:
            raw_asset = db.query(RawAssets).filter(RawAssets.id == str(raw_id)).first()
            if raw_asset:
                db.delete(raw_asset)
            deleted_count += 1

    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_BULK_ACTION",
                    resource_type="RAW_ASSETS", resource_id="BULK",
                    details=f"Bulk action: {deleted_count} deleted, {archived_count} archived.")
    db.commit()
    return {"message": f"Processed successfully: {deleted_count} deleted, {archived_count} archived."}


###################################
# ---  THE PROMOTION ENGINE   --- #
###################################
def promote_raw_assets_to_pool(db: Session, req: BulkAssetRequest, current_user: dict):
    promoted = 0
    for raw_id in req.raw_asset_ids:
        existing = db.query(Assets).filter(Assets.raw_asset_id == str(raw_id)).first()
        if existing:
            continue

        raw_asset = db.query(RawAssets).filter(RawAssets.id == str(raw_id)).first()
        if not raw_asset:
            continue

        new_pool_asset = Assets(
            raw_asset_id=str(raw_id),
            name=raw_asset.name,
            country_id=raw_asset.country_id,
            service_forecast_id=raw_asset.service_forecast_id,
            category_id=raw_asset.category_id,
            asset_type_id=raw_asset.asset_type_id
        )
        db.add(new_pool_asset)
        insert_asset_history(db, str(raw_id), str(current_user["id"]), "PROMOTED", "Asset moved to the Active testing pool.")
        promoted += 1

    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="RAW_ASSET_PROMOTED",
                    resource_type="RAW_ASSETS", resource_id="BULK", details=f"{promoted} assets promoted.")
    db.commit()
    return {"message": f"Successfully promoted {promoted} assets to the Active Pool."}


def bulk_update_service_lane(db: Session, req: BulkServiceUpdateRequest, current_user: dict):
    service_id = str(req.service_lane_id)
    service_obj = db.query(ServiceLanes).filter(ServiceLanes.id == service_id).first()
    s_name = service_obj.name if service_obj else "Unknown"

    for asset_id in req.asset_ids:
        pool_asset = db.query(Assets).filter(Assets.id == str(asset_id)).first()
        if not pool_asset:
            continue

        pool_asset.service_forecast_id = service_id

        raw_asset = db.query(RawAssets).filter(RawAssets.id == pool_asset.raw_asset_id).first()
        if raw_asset:
            raw_asset.service_forecast_id = service_id
            raw_asset.update_date = aware_utcnow()

        insert_asset_history(db, str(pool_asset.raw_asset_id), str(current_user["id"]), "UPDATED",
                             f"Service Lane bulk updated to '{s_name}'.")

    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"],
                    action="ASSET_UPDATED_SERVICE_LANE_BULK", resource_type="ASSETS", resource_id="BULK",
                    details=f"Bulk updated service lane to {service_id}.")
    db.commit()
    return {"message": f"Successfully updated service lane for {len(req.asset_ids)} assets."}


###################################
# ---    ACTIVE ASSET POOL    --- #
###################################
def get_active_asset_pool(db: Session, year: int, current_user: dict):
    if current_user['role'] == 'pentester':
        raise HTTPException(status_code=403, detail="Pentesters cannot view the unassigned asset inventory.")

    is_assigned_sub = db.query(func.count(TestAssets.test_id) > 0)\
        .select_from(TestAssets)\
        .join(Tests, TestAssets.test_id == Tests.id)\
        .filter(
            TestAssets.asset_id == Assets.id,
            or_(
                Tests.stages == TestStages.NOT_PLANNED,
                and_(
                    Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS]),
                    Tests.start_year == year
                )
            )
        ).correlate(Assets).scalar_subquery()

    in_backlog_sub = db.query(func.count(TestAssets.test_id) > 0)\
        .select_from(TestAssets)\
        .join(Tests, TestAssets.test_id == Tests.id)\
        .filter(
            TestAssets.asset_id == Assets.id,
            Tests.stages == TestStages.NOT_PLANNED
        ).correlate(Assets).scalar_subquery()

    completed_count_sub = db.query(func.count(TestAssets.test_id))\
        .select_from(TestAssets)\
        .join(Tests, TestAssets.test_id == Tests.id)\
        .filter(
            TestAssets.asset_id == Assets.id,
            Tests.stages == TestStages.COMPLETED,
            Tests.start_year == year
        ).correlate(Assets).scalar_subquery()

    max_val_sub = db.query(func.max(literal_column("val")))\
        .select_from(func.unnest(Assets.archived_years).alias("val"))\
        .correlate(Assets).scalar_subquery()

    is_archived_this_year_expr = and_(
        Assets.archived_years.isnot(None),
        or_(
            Assets.archived_years.any(year),
            and_(
                Assets.is_archived == True,
                year > max_val_sub
            )
        )
    )

    query = db.query(
        Assets.id,
        Assets.raw_asset_id,
        RawAssets.name,
        RawAssets.country_id,
        Country.name.label("country"),
        ServiceLanes.name.label("service_name"),
        ServiceCategories.name.label("category_name"),
        AssetTypes.name.label("asset_type_name"),
        RawAssets.duplicate_allowed,
        RawAssets.kiss24_asset_id,
        RawAssets.is_kpi,
        RawAssets.is_critical,
        is_assigned_sub.label("is_assigned"),
        in_backlog_sub.label("in_backlog"),
        completed_count_sub.label("completed_count"),
        is_archived_this_year_expr.label("is_archived_this_year")
    ).join(RawAssets, Assets.raw_asset_id == RawAssets.id)\
     .outerjoin(Country, RawAssets.country_id == Country.id)\
     .outerjoin(ServiceLanes, RawAssets.service_forecast_id == ServiceLanes.id)\
     .outerjoin(ServiceCategories, RawAssets.category_id == ServiceCategories.id)\
     .outerjoin(AssetTypes, RawAssets.asset_type_id == AssetTypes.id)

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        if lane_id:
            query = query.filter(RawAssets.service_forecast_id == str(lane_id))
        else:
            query = query.filter(RawAssets.service_forecast_id == '00000000-0000-0000-0000-000000000000')

    rows = query.order_by(RawAssets.name.asc()).all()

    return [
        {
            "id": str(r[0]),
            "raw_asset_id": str(r[1]),
            "name": r[2],
            "country_id": str(r[3]) if r[3] else None,
            "country": r[4],
            "service_name": r[5],
            "category_name": r[6],
            "asset_type_name": r[7],
            "duplicate_allowed": r[8],
            "kiss24_asset_id": r[9],
            "is_kpi": r[10],
            "is_critical": r[11],
            "is_assigned": r[12],
            "in_backlog": r[13],
            "completed_count": r[14],
            "is_archived_this_year": r[15]
        }
        for r in rows
    ]


def remove_from_active_pool(db: Session, asset_id: str, year: int, current_user: dict):
    pool_asset = db.query(Assets).filter(Assets.id == asset_id).first()
    if not pool_asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    raw_asset_id = str(pool_asset.raw_asset_id)
    current_years = list(pool_asset.archived_years) if pool_asset.archived_years else []

    completed_count = db.query(func.count(TestAssets.test_id))\
        .select_from(TestAssets)\
        .join(Tests, TestAssets.test_id == Tests.id)\
        .filter(TestAssets.asset_id == asset_id, Tests.stages == TestStages.COMPLETED).scalar() or 0

    if completed_count > 0:
        if year not in current_years:
            current_years.append(year)
        pool_asset.archived_years = current_years
        pool_asset.is_archived = True
        action_msg = f"Archived asset for {year} onwards (Preserving {completed_count} completed tests)."
        insert_asset_history(db, raw_asset_id, str(current_user["id"]), "ARCHIVED", f"Asset archived from active pool in {year}.")
    else:
        db.delete(pool_asset)
        action_msg = "Asset safely returned to raw data pool."
        insert_asset_history(db, raw_asset_id, str(current_user["id"]), "RETURNED", "Asset safely returned to Raw Pool (0 tests).")

    db.commit()
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="ASSET_REMOVE_FROM_ACTIVE_POOL",
                    resource_type="ASSETS", resource_id=str(asset_id), details=action_msg)
    return {"message": action_msg}


###################################
# --- ServiceNow integrations --- #
###################################
def full_background_sync_wrapper(user_id: str, user_role: str):
    log_audit_event(user_id=user_id, role=user_role, action="SERVICE_NOW_SYNC_THREAD_START",
                    resource_type="INTEGRATION", details="Background thread launched.")
    try:
        snow_records = fetch_raw_snow_data(user_id, user_role)
        if not snow_records:
            log_audit_event(user_id=user_id, role=user_role, action="SERVICE_NOW_SYNC_CRASH",
                            resource_type="INTEGRATION", details="Fetch returned 0 records. Aborting.")
            return
        db = SessionLocal()
        try:
            process_and_sync_snow_data(db, snow_records, user_id, user_role)
        finally:
            db.close()
    except Exception as e:
        log_audit_event(user_id=user_id, role=user_role, action="SERVICE_NOW_SYNC_CRASH", resource_type="INTEGRATION",
                        details=f"CRITICAL ERROR: {str(e)}")


def get_last_snow_sync(db: Session, current_user: dict):
    # .scalar() returns the actual datetime object, or None if the table is empty!
    last_sync = db.query(func.max(RawAssetsSnowMetadata.last_snow_sync)).scalar()

    return {"last_sync": last_sync}


###################################
# --- LEgacy --- #
###################################
def process_excel_import_sync(contents: bytes, filename: str, current_user: dict):
    db = SessionLocal()
    try:
        df = pd.read_csv(io.BytesIO(contents)) if filename.lower().endswith('.csv') else pd.read_excel(io.BytesIO(contents))
        df = df.fillna('')

        types_map = {at.name.lower(): str(at.id) for at in db.query(AssetTypes).all() if at.name}
        countries_map = {}
        for c in db.query(Country).all():
            if c.name: countries_map[c.name.lower()] = str(c.id)
            if c.code: countries_map[c.code.lower()] = str(c.id)
        services_map = {s.name.lower(): str(s.id) for s in db.query(ServiceLanes).all() if s.name}
        categories_map = {cat.name.lower(): str(cat.id) for cat in db.query(ServiceCategories).all() if cat.name}
        existing_ids = {str(r[0]) for r in db.query(RawAssets.id).all()}

        success_count, failed_items = 0, []

        for _, row in df.iterrows():
            asset_id = sanitize_csv_injection(str(row.get('ID', '')).strip())
            name = sanitize_csv_injection(str(row.get('Name', '')).strip())
            if not name: continue

            type_str = sanitize_csv_injection(str(row.get('Asset Type', '')).strip().lower())
            country_str = sanitize_csv_injection(str(row.get('Country', '')).strip().lower())

            type_id = types_map.get(type_str)
            country_id = countries_map.get(country_str)

            if not type_id or not country_id:
                failed_items.append(f"{name} (Unknown Type/Country)")
                continue

            try:
                new_id = asset_id if asset_id else str(uuid.uuid4())
                if asset_id and asset_id in existing_ids:
                    raw_asset = db.query(RawAssets).filter(RawAssets.id == asset_id).first()
                    if raw_asset:
                        raw_asset.name = name
                        raw_asset.update_date = aware_utcnow()
                        insert_asset_history(db, asset_id, str(current_user["id"]), "IMPORTED", "Asset metadata updated via bulk Excel import.")
                else:
                    new_raw_asset = RawAssets(
                        id=new_id,
                        name=name,
                        country_id=country_id,
                        asset_type_id=type_id,
                        create_date=aware_utcnow()
                    )
                    db.add(new_raw_asset)
                    insert_asset_history(db, new_id, str(current_user["id"]), "IMPORTED", "Asset created via bulk Excel import.")
                    existing_ids.add(new_id)

                db.flush()
                success_count += 1
            except Exception:
                db.rollback()
                failed_items.append(f"{name} (DB Error)")

        db.commit()
        return success_count, failed_items
    except Exception as e:
        db.rollback()
        return 0, [f"File formatting error: {str(e)}"]
    finally:
        db.close()