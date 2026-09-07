from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, UUID4
from typing import Optional
from database import get_db_cursor
from routers.auth import get_current_user, require_admin, require_admin_or_read_only
from schema import CountryBase
import uuid
from datetime import datetime
from audit_logger import log_audit_event


router = APIRouter(prefix="/api/countries", tags=["Countries"])


@router.get("/")
def get_countries(current_user: dict = Depends(get_current_user), cursor = Depends(get_db_cursor)):

    if current_user.get('role') == 'pentester':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=f"{current_user.get('role')} cannot access country data.")

    cursor.execute("""
        SELECT c.id, c.code, c.name, c.is_active, c.region_id, r.name as region_name, c.kiss24_uuid, c.is_team
        FROM countries c 
        LEFT JOIN regions r ON c.region_id = r.id 
        ORDER BY c.code
    """)
    return [{
        "id": r[0],
        "code": r[1],
        "name": r[2],
        "is_active": r[3],
        "region_id": r[4],
        "region_name": r[5],
        "kiss24_uuid": r[6],
        "is_team": r[7]
    } for r in cursor.fetchall()]


@router.post("/", summary="[Admin Only]")
def create_country(c: CountryBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Create Country
    """
    reg_id = str(c.region_id) if c.region_id else None
    new_country_id = str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO countries (id, code, name, region_id, is_active, kiss24_uuid, is_team) VALUES (%s, %s, %s, %s, %s, %s, %s)",
            (new_country_id, c.code, c.name, reg_id, c.is_active, c.kiss24_uuid, c.is_team)
        )
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="COUNTRY_CREATED",
            resource_type="COUNTRY",
            resource_id=str(new_country_id),
            details=f"Country {c.name} with ID {new_country_id} has been created in region {reg_id}."
        )

        return {"id": new_country_id, "message": "Country created successfully."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database error (Code might already exist)")


@router.put("/{country_id}", summary="[Admin Only]")
def update_country(country_id: str, c: CountryBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Update Country
    """
    cursor.execute(
        "UPDATE countries SET code=%s, name=%s, region_id=%s, is_active=%s, kiss24_uuid=%s, is_team=%s WHERE id=%s",
        (c.code, c.name, c.region_id, c.is_active, c.kiss24_uuid, c.is_team, country_id)
    )

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="COUNTRY_UPDATED",
        resource_type="COUNTRY",
        resource_id=str(country_id),
        details=f"Country with ID {country_id} has been updated."
    )

    cursor.connection.commit()
    return {"message": "Country updated successfully."}


@router.delete("/{country_id}", summary="[Admin Only]")
def delete_country(country_id: str, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Delete Country
    """
    cursor.execute("DELETE FROM countries WHERE id = %s", (country_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="COUNTRY_DELETED",
        resource_type="COUNTRY",
        resource_id=str(country_id),
        details=f"Country with ID {country_id} has been deleted."
    )

    return {"message": "Country deleted."}


@router.get("/analytics", summary="[Admin Only]")
def get_country_analytics(year: Optional[int] = None, current_user: dict = Depends(require_admin_or_read_only),
                          cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Get Country Analytics
    """
    if not year:
        year = datetime.now().year

    # Massive Aggregation Query!
    cursor.execute("""
        SELECT 
            c.id, c.code, c.name, r.name as region_name,
            (SELECT COUNT(*) FROM raw_assets ra WHERE ra.country_id = c.id) as raw_assets_count,

            (SELECT COUNT(*) FROM assets a 
             JOIN raw_assets ra ON a.raw_asset_id = ra.id 
             WHERE ra.country_id = c.id) as pool_assets_count,

            (SELECT COUNT(*) FROM test_assets ta
             JOIN tests t ON ta.test_id = t.id
             JOIN assets a ON ta.asset_id = a.id
             JOIN raw_assets ra ON a.raw_asset_id = ra.id
             WHERE ra.country_id = c.id 
               AND t.stages::text = 'COMPLETED' 
               AND t.start_year = %s) as completed_tests_count,

            (SELECT COUNT(*) FROM test_assets ta
             JOIN tests t ON ta.test_id = t.id
             JOIN assets a ON ta.asset_id = a.id
             JOIN raw_assets ra ON a.raw_asset_id = ra.id
             WHERE ra.country_id = c.id 
               AND t.stages::text IN ('SCHEDULED', 'IN_PROGRESS') 
               AND t.start_year = %s) as active_tests_count

        FROM countries c
        LEFT JOIN regions r ON c.region_id = r.id
        WHERE c.is_active = TRUE
        ORDER BY completed_tests_count DESC, pool_assets_count DESC, c.name ASC
    """, (year, year))

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.get("/available-years", summary="[Admin Only]")
def get_available_years(current_user: dict = Depends(require_admin_or_read_only), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Get Available Years
    """
    cursor.execute("""
        SELECT DISTINCT start_year 
        FROM tests 
        WHERE start_year IS NOT NULL 
        ORDER BY start_year DESC
    """)
    years = [r[0] for r in cursor.fetchall()]
    if not years:
        years = [datetime.now().year]
    return years


@router.get("/dashboard", summary="[Admin Only]")
def get_dashboard_analytics(year: Optional[int] = None, country_id: Optional[str] = None,
                            region_id: Optional[str] = None, service_lane_id: Optional[str] = None,
                            current_user: dict = Depends(require_admin_or_read_only),
                            cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Get Dashboard Analytics
    """
    if not year:
        year = datetime.now().year

    # --- KPI QUERY ---
    kpi_query = f"""
        SELECT 
            COUNT(DISTINCT ra.id) as raw,
            COUNT(DISTINCT a.id) as pool,
            COUNT(DISTINCT CASE WHEN t.stages::text = 'COMPLETED' AND t.start_year = %s THEN t.id END) as completed,
            COUNT(DISTINCT CASE WHEN t.stages::text IN ('NOT_PLANNED', 'SCHEDULED', 'IN_PROGRESS') THEN t.id END) as backlog,
            COUNT(DISTINCT CASE WHEN t.stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND t.start_year = %s THEN t.id END) as planned,
            COUNT(DISTINCT CASE WHEN t.stages::text IN ('NOT_PLANNED', 'SCHEDULED', 'IN_PROGRESS') AND (t.start_year IS NULL OR t.start_year != %s) THEN t.id END) as true_backlog,
            COUNT(DISTINCT CASE 
                WHEN (t.stages::text = 'COMPLETED' AND t.start_year = %s) 
                OR (t.stages::text IN ('NOT_PLANNED', 'SCHEDULED', 'IN_PROGRESS')) 
                THEN t.id 
            END) as total_tests_year,
            -- SCOPED STOPPED TESTS BY YEAR
            COUNT(DISTINCT CASE WHEN t.stages::text = 'STOPPED' AND t.start_year = %s THEN t.id END) as stopped
        FROM raw_assets ra
        {'LEFT JOIN countries c ON ra.country_id = c.id' if region_id else ''}
        LEFT JOIN assets a ON ra.id = a.raw_asset_id
        LEFT JOIN test_assets ta ON a.id = ta.asset_id
        LEFT JOIN tests t ON ta.test_id = t.id
        WHERE 1=1
    """

    kpi_params = [year, year, year, year, year] # 5 parameters now

    if country_id:
        kpi_query += " AND ra.country_id = %s"
        kpi_params.append(country_id)
    if region_id:
        kpi_query += " AND c.region_id = %s"
        kpi_params.append(region_id)
    if service_lane_id:
        kpi_query += " AND t.service_lane_id = %s"
        kpi_params.append(service_lane_id)

    cursor.execute(kpi_query, tuple(kpi_params))
    kpi_row = cursor.fetchone()
    kpis = {
        "raw": kpi_row[0], "pool": kpi_row[1], "completed": kpi_row[2],
        "backlog": kpi_row[3], "planned": kpi_row[4], "true_backlog": kpi_row[5],
        "total_tests_year": kpi_row[6], "stopped": kpi_row[7]
    }

    # --- PIE CHART QUERY ---
    pie_query = f"""
        SELECT COALESCE(sl.name, 'Not Set') as name, COUNT(DISTINCT t.id) as value
        FROM tests t
        JOIN test_assets ta ON t.id = ta.test_id
        JOIN assets a ON ta.asset_id = a.id
        JOIN raw_assets ra ON a.raw_asset_id = ra.id
        {'LEFT JOIN countries c ON ra.country_id = c.id' if region_id else ''}
        LEFT JOIN services_lanes sl ON t.service_lane_id = sl.id
        WHERE 1=1
          AND t.stages::text != 'STOPPED'
    """
    pie_params = []
    if country_id:
        pie_query += " AND ra.country_id = %s"
        pie_params.append(country_id)
    if region_id:
        pie_query += " AND c.region_id = %s"
        pie_params.append(region_id)
    if service_lane_id:
        pie_query += " AND t.service_lane_id = %s"
        pie_params.append(service_lane_id)

    pie_query += " GROUP BY sl.name ORDER BY value DESC"
    cursor.execute(pie_query, tuple(pie_params))
    pie_data = [{"name": r[0], "value": r[1]} for r in cursor.fetchall()]

    # --- TREND CHART QUERY ---
    trend_query = f"""
        SELECT 
            EXTRACT(MONTH FROM TO_DATE(t.start_year::text || '0101', 'YYYYMMDD') + ((t.start_week - 1) * 7)) as month_num,
            COUNT(DISTINCT t.id) as tests
        FROM tests t
        JOIN test_assets ta ON t.id = ta.test_id
        JOIN assets a ON ta.asset_id = a.id
        JOIN raw_assets ra ON a.raw_asset_id = ra.id
        {'LEFT JOIN countries c ON ra.country_id = c.id' if region_id else ''}
        WHERE t.start_year = %s 
          AND t.stages::text IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED')
    """
    trend_params = [year]
    if country_id:
        trend_query += " AND ra.country_id = %s"
        trend_params.append(country_id)
    if region_id:
        trend_query += " AND c.region_id = %s"
        trend_params.append(region_id)
    if service_lane_id:
        trend_query += " AND t.service_lane_id = %s"
        trend_params.append(service_lane_id)

    trend_query += " GROUP BY month_num ORDER BY month_num"
    cursor.execute(trend_query, tuple(trend_params))

    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    monthly_data = {int(r[0]): r[1] for r in cursor.fetchall() if r[0]}
    trend_data = [{"month": months[i - 1], "tests": monthly_data.get(i, 0)} for i in range(1, 13)]

    return {"kpis": kpis, "pie_data": pie_data, "trend_data": trend_data}