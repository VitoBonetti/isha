import uuid
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func, case, and_, or_, cast, String
from sqlalchemy.exc import IntegrityError
from models.territories import Country, Region
from models.raw_assets import RawAssets
from models.assets import Assets
from models.tests import Tests, TestAssets, TestStages
from models.services import ServiceLanes
from audit_logger import log_audit_event


def get_countries(db: Session, current_user: dict):
    if current_user.get('role') == 'pentester':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                            detail=f"{current_user.get('role')} cannot access country data.")

    countries = (db.query(Country, Region.name.label("region_name"))
                 .outerjoin(Region, Country.region_id == Region.id)
                 .order_by(Country.code.asc()).all())

    return [{
        "id": str(c.Country.id),
        "code": c.Country.code,
        "name": c.Country.name,
        "is_active": c.Country.is_active,
        "region_id": str(c.Country.region_id) if c.Country.region_id else None,
        "region_name": c.region_name,
        "kiss24_uuid": c.Country.kiss24_uuid,
        "is_team": c.Country.is_team
    } for c in countries]


def create_country(db: Session, c, current_user: dict):
    reg_id = str(c.region_id) if c.region_id else None

    try:
        new_country = Country(
            code=c.code,
            name=c.name,
            region_id=reg_id,
            is_active=c.is_active,
            kiss24_uuid=c.kiss24_uuid,
            is_team=c.is_team
        )
        db.add(new_country)
        db.commit()
        db.refresh(new_country)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="COUNTRY_CREATED",
            resource_type="COUNTRY",
            resource_id=str(new_country.id),
            details=f"Country {new_country.name} with ID {new_country.id} has been created in region {reg_id}."
        )

        return {"id": str(new_country.id), "message": "Country created successfully."}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database error (Code might already exist)")


def update_country(db: Session, country_id: str, c, current_user: dict):
    country = db.query(Country).filter(Country.id == country_id).first()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found.")

    country.code = c.code
    country.name = c.name
    country.region_id = str(c.region_id) if c.region_id else None
    country.is_active = c.is_active
    country.kiss24_uuid = c.kiss24_uuid
    country.is_team = c.is_team

    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="COUNTRY_UPDATED",
        resource_type="COUNTRY",
        resource_id=str(country_id),
        details=f"Country with ID {country_id} has been updated."
    )

    return {"message": "Country updated successfully."}


def delete_country(db: Session, country_id: str, current_user: dict):
    country = db.query(Country).filter(Country.id == country_id).first()
    if not country:
        raise HTTPException(status_code=404, detail="Country not found.")

    db.delete(country)
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="COUNTRY_DELETED",
        resource_type="COUNTRY",
        resource_id=str(country_id),
        details=f"Country with ID {country_id} has been deleted."
    )

    return {"message": "Country deleted."}


def get_country_analytics(db: Session, year: int):
    if not year:
        year = datetime.now().year

    # Define the isolated subqueries
    raw_subq = (db.query(func.count(RawAssets.id))
                .filter(RawAssets.country_id == Country.id).correlate(Country).scalar_subquery())

    pool_subq = (db.query(func.count(Assets.id))
                 .join(RawAssets, Assets.raw_asset_id == RawAssets.id)
                 .filter(RawAssets.country_id == Country.id).correlate(Country).scalar_subquery())

    completed_subq = (db.query(func.count(TestAssets.test_id))
                      .join(Tests, TestAssets.test_id == Tests.id)
                      .join(Assets, TestAssets.asset_id == Assets.id)
                      .join(RawAssets, Assets.raw_asset_id == RawAssets.id)
                      .filter(RawAssets.country_id == Country.id, Tests.stages == TestStages.COMPLETED, Tests.start_year == year)
                      .correlate(Country).scalar_subquery())

    active_subq = (db.query(func.count(TestAssets.test_id))
                   .join(Tests, TestAssets.test_id == Tests.id)
                   .join(Assets, TestAssets.asset_id == Assets.id)
                   .join(RawAssets, Assets.raw_asset_id == RawAssets.id)
                   .filter(RawAssets.country_id == Country.id, Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS]),
                           Tests.start_year == year)
                   .correlate(Country).scalar_subquery())

    # Build the main query
    results = (db.query(
        Country.id, Country.code, Country.name, Region.name.label("region_name"),
        raw_subq.label("raw_assets_count"),
        pool_subq.label("pool_assets_count"),
        completed_subq.label("completed_tests_count"),
        active_subq.label("active_tests_count")
    ).outerjoin(Region, Country.region_id == Region.id)
               .filter(Country.is_active == True)
               .order_by(completed_subq.desc(), pool_subq.desc(), Country.name.asc()).all())

    return [{
        "id": str(r.id), "code": r.code, "name": r.name, "region_name": r.region_name,
        "raw_assets_count": r.raw_assets_count or 0,
        "pool_assets_count": r.pool_assets_count or 0,
        "completed_tests_count": r.completed_tests_count or 0,
        "active_tests_count": r.active_tests_count or 0
    } for r in results]


def get_available_years(db: Session):
    years = (db.query(Tests.start_year)
             .filter(Tests.start_year.isnot(None))
             .distinct()
             .order_by(Tests.start_year.desc()).all())

    if not years:
        return [datetime.now().year]
    return [r[0] for r in years]


def get_dashboard_analytics(db: Session, year: int, country_id: str, region_id: str, service_lane_id: str):
    if not year:
        year = datetime.now().year

    # --- KPI QUERY ---
    kpi_query = (db.query(
        func.count(func.distinct(RawAssets.id)).label("raw"),
        func.count(func.distinct(Assets.id)).label("pool"),
        func.count(func.distinct(
            case((and_(Tests.stages == TestStages.COMPLETED, Tests.start_year == year), Tests.id)))).label("completed"),
        func.count(func.distinct(case(
            (Tests.stages.in_([TestStages.NOT_PLANNED, TestStages.SCHEDULED, TestStages.IN_PROGRESS]),
             Tests.id)))).label("backlog"),
        func.count(func.distinct(case(
            (and_(Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS]), Tests.start_year == year),
             Tests.id)))).label("planned"),
        func.count(func.distinct(case(
            (and_(Tests.stages.in_([TestStages.NOT_PLANNED, TestStages.SCHEDULED, TestStages.IN_PROGRESS]),
                  or_(Tests.start_year == None, Tests.start_year != year)), Tests.id)))).label("true_backlog"),
        func.count(func.distinct(case((or_(and_(Tests.stages == TestStages.COMPLETED, Tests.start_year == year),
                                           Tests.stages.in_(
                                               [TestStages.NOT_PLANNED, TestStages.SCHEDULED, TestStages.IN_PROGRESS])),
                                       Tests.id)))).label("total_tests_year"),
        func.count(
            func.distinct(case((and_(Tests.stages == TestStages.STOPPED, Tests.start_year == year), Tests.id)))).label(
            "stopped")
    ).select_from(RawAssets)
                 .outerjoin(Assets, RawAssets.id == Assets.raw_asset_id)
                 .outerjoin(TestAssets, Assets.id == TestAssets.asset_id)
                 .outerjoin(Tests, TestAssets.test_id == Tests.id))

    if region_id: kpi_query = kpi_query.outerjoin(Country, RawAssets.country_id == Country.id)
    if country_id: kpi_query = kpi_query.filter(RawAssets.country_id == country_id)
    if region_id: kpi_query = kpi_query.filter(Country.region_id == region_id)
    if service_lane_id: kpi_query = kpi_query.filter(Tests.service_lane_id == service_lane_id)

    kpi_row = kpi_query.first()
    kpis = {
        "raw": kpi_row.raw, "pool": kpi_row.pool, "completed": kpi_row.completed,
        "backlog": kpi_row.backlog, "planned": kpi_row.planned, "true_backlog": kpi_row.true_backlog,
        "total_tests_year": kpi_row.total_tests_year, "stopped": kpi_row.stopped
    }

    # --- PIE CHART QUERY ---
    pie_query = (db.query(
        func.coalesce(ServiceLanes.name, 'Not Set').label("name"),
        func.count(func.distinct(Tests.id)).label("value")
    ).select_from(Tests)
                 .join(TestAssets, Tests.id == TestAssets.test_id)
                 .join(Assets, TestAssets.asset_id == Assets.id)
                 .join(RawAssets, Assets.raw_asset_id == RawAssets.id))

    if region_id: pie_query = pie_query.outerjoin(Country, RawAssets.country_id == Country.id)

    pie_query = (pie_query.outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                 .filter(Tests.stages != TestStages.STOPPED))

    if country_id: pie_query = pie_query.filter(RawAssets.country_id == country_id)
    if region_id: pie_query = pie_query.filter(Country.region_id == region_id)
    if service_lane_id: pie_query = pie_query.filter(Tests.service_lane_id == service_lane_id)

    pie_data = [{"name": r.name, "value": r.value} for r in pie_query.group_by(ServiceLanes.name).order_by(func.count(func.distinct(Tests.id)).desc()).all()]

    # --- TREND CHART QUERY ---
    trend_query = (db.query(
        Tests.start_year,
        Tests.start_week,
        func.count(func.distinct(Tests.id)).label("tests")
    ).select_from(Tests)
                   .join(TestAssets, Tests.id == TestAssets.test_id)
                   .join(Assets, TestAssets.asset_id == Assets.id)
                   .join(RawAssets, Assets.raw_asset_id == RawAssets.id))

    if region_id: trend_query = trend_query.outerjoin(Country, RawAssets.country_id == Country.id)

    trend_query = trend_query.filter(
        Tests.start_year == year,
        Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS, TestStages.COMPLETED])
    )

    if country_id: trend_query = trend_query.filter(RawAssets.country_id == country_id)
    if region_id: trend_query = trend_query.filter(Country.region_id == region_id)
    if service_lane_id: trend_query = trend_query.filter(Tests.service_lane_id == service_lane_id)

    # Group safely by the base columns!
    trend_results = trend_query.group_by(Tests.start_year, Tests.start_week).all()

    # Calculate the months dynamically in Python
    monthly_data = {}
    for r in trend_results:
        if r.start_year and r.start_week:
            try:
                # Convert ISO year and week to a standard month
                dt = datetime.fromisocalendar(r.start_year, r.start_week, 1)
                m = dt.month
                monthly_data[m] = monthly_data.get(m, 0) + r.tests
            except ValueError:
                continue

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    trend_data = [{"month": months[i - 1], "tests": monthly_data.get(i, 0)} for i in range(1, 13)]

    return {"kpis": kpis, "pie_data": pie_data, "trend_data": trend_data}