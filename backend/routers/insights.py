from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from database import get_db_cursor
from typing import Optional
from routers.auth import require_admin

router = APIRouter(prefix="/api/insights", tags=["Insights"])


@router.get("/", summary="[Admin Only]")
def get_yearly_insights(year: Optional[int] = None, current_user: dict = Depends(require_admin),
                        cursor=Depends(get_db_cursor)):
    if not year: year = datetime.now().year

    # --- A & B: CAPACITY & EVENT CONSUMPTION ---
    # We fetch all users and their events for the year to calculate exact available credits
    cursor.execute("SELECT id, base_capacity, start_year, start_week, end_year, end_week FROM users")
    users = cursor.fetchall()

    total_gross_credits = 0.0
    total_event_cost = {"national_holiday": 0.0, "team_day": 0.0, "personal_time_off": 0.0, "sick_day": 0.0}

    for u_id, base_cap, s_year, s_week, e_year, e_week in users:
        base = float(base_cap or 0.0)

        # Calculate active weeks in this year
        start = s_week if s_year == year else 1
        end = e_week if e_year == year else 52  # Simplified 52-week year

        if (s_year and year < s_year) or (e_year and year > e_year):
            continue  # Not active this year

        active_weeks = max(0, end - start + 1)
        total_gross_credits += (active_weeks * base)

        # Calculate event costs for this user
        cursor.execute("""
            SELECT event_type, start_date, end_date FROM events 
            WHERE (user_id = %s OR event_type IN ('team_day', 'national_holiday'))
              AND EXTRACT(YEAR FROM start_date) = %s
        """, (str(u_id), year))

        for e_type, e_start, e_end in cursor.fetchall():
            days_off = (e_end - e_start).days + 1
            cost = days_off * (base * 0.2)  # 1 day = 20% of weekly capacity
            if e_type in total_event_cost:
                total_event_cost[e_type] += cost

    net_credits = total_gross_credits - sum(total_event_cost.values())

    # --- C, D, & E: SERVICE LANE & ASSET AGGREGATIONS ---
    cursor.execute("""
        SELECT 
            sl.id as service_id, sl.name as service_name, sl.default_credits, sl.theme_color,

            -- C: Real Assigned Credits this year
            COALESCE((
                SELECT SUM(a.allocated_credits) FROM assignments a 
                JOIN tests t ON a.test_id = t.id 
                WHERE t.service_lane_id = sl.id AND a.year = %s
            ), 0) as real_assigned_credits,

            -- Total Assets in Pool for this service
            (SELECT COUNT(*) FROM assets ast 
             JOIN raw_assets ra ON ast.raw_asset_id = ra.id 
             WHERE ra.service_forecast_id = sl.id) as total_pool_assets,

            -- Completed Tests this year
            (SELECT COUNT(*) FROM tests t 
             WHERE t.service_lane_id = sl.id AND t.start_year = %s AND t.stages::text = 'COMPLETED') as completed_tests,

            -- Planned/Active Tests
            (SELECT COUNT(*) FROM tests t 
             WHERE t.service_lane_id = sl.id AND t.start_year = %s AND t.stages::text IN ('SCHEDULED', 'IN_PROGRESS')) as planned_tests

        FROM services_lanes sl
        WHERE sl.is_active = TRUE
    """, (year, year, year))

    services_data = []
    columns = [col[0] for col in cursor.description]
    for row in cursor.fetchall():
        s_dict = dict(zip(columns, row))

        # Calculate Unplanned/Ready assets
        s_dict['unplanned_assets'] = max(0, s_dict['total_pool_assets'] - s_dict['completed_tests'] - s_dict[
            'planned_tests'])

        # D: Forecasted Credits (Unplanned Assets * Default Credits)
        s_dict['forecast_credits'] = s_dict['unplanned_assets'] * float(s_dict['default_credits'] or 0.0)

        # Fetch Category Breakdown for this service
        cursor.execute("""
            SELECT id, name, target_goal,
                (SELECT COUNT(*) FROM assets ast JOIN raw_assets ra ON ast.raw_asset_id = ra.id WHERE ra.category_id = sc.id) as cat_pool_count,
                (SELECT COUNT(DISTINCT t.id) FROM tests t JOIN test_assets ta ON t.id = ta.test_id JOIN assets ast ON ta.asset_id = ast.id JOIN raw_assets ra ON ast.raw_asset_id = ra.id 
                 WHERE ra.category_id = sc.id AND t.start_year = %s AND t.stages::text = 'COMPLETED') as cat_completed
            FROM service_categories sc WHERE service_lane_id = %s
        """, (year, str(s_dict['service_id'])))

        cat_cols = [c[0] for c in cursor.description]
        s_dict['categories'] = [dict(zip(cat_cols, c_row)) for c_row in cursor.fetchall()]
        services_data.append(s_dict)

    return {
        "year": year,
        "capacity": {
            "gross": total_gross_credits,
            "net": net_credits,
            "events": total_event_cost
        },
        "services": services_data
    }