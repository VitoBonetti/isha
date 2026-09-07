from fastapi import APIRouter, Depends
from datetime import datetime, timedelta
from database import get_db_cursor
from typing import Optional
from routers.auth import require_admin, require_admin_or_read_only

router = APIRouter(prefix="/api/insights", tags=["Insights"])


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


@router.get("/", summary="[Admin Only]")
def get_yearly_insights(year: Optional[int] = None, current_user: dict = Depends(require_admin_or_read_only),
                        cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Get Yearly Insights
    """
    if not year: year = datetime.now().year

    # --- DETERMINE PAST WEEKS FOR "WASTED" MATH ---
    current_year_real = datetime.now().year
    current_week_real = datetime.now().isocalendar()[1]

    past_weeks = []
    if year < current_year_real:
        # If looking at a past year, all weeks are "past"
        d = datetime(year, 12, 28)
        max_w = d.isocalendar()[1]
        past_weeks = list(range(1, max_w + 1))
    elif year == current_year_real:
        # If current year, weeks 1 to (current_week - 1) are "past"
        past_weeks = list(range(1, current_week_real))

    # ---  GROSS CAPACITY, TIME OFF & WASTED ---
    # NEW: Fetched 'name' to use in the wasted breakdown
    cursor.execute("SELECT id, name, base_capacity, start_year, start_week, end_year, end_week, location_id FROM users")
    users = cursor.fetchall()

    total_gross_credits = 0.0
    events_cost = {"National Holiday": 0.0, "Team Day": 0.0, "Personal Time Off": 0.0, "Sick Day": 0.0}
    event_mapping = {"national_holiday": "National Holiday", "team_day": "Team Day",
                     "personal_time_off": "Personal Time Off", "sick_day": "Sick Day"}

    wasted_breakdown = {}
    total_wasted = 0.0

    # Dynamically calculate total ISO weeks in the target year (52 or 53)
    total_weeks_in_year = datetime(year, 12, 28).isocalendar()[1]

    for u_id, u_name, base_cap, s_year, s_week, e_year, e_week, loc_id in users:
        base = float(base_cap or 0.0)
        start = s_week if s_year == year else 1
        end = e_week if e_year == year else total_weeks_in_year
        if (s_year and year < s_year) or (e_year and year > e_year): continue

        active_weeks = max(0, end - start + 1)
        total_gross_credits += (active_weeks * base)

        safe_loc_id = str(loc_id) if loc_id else None

        cursor.execute("""
            SELECT event_type, start_date, end_date FROM events 
            WHERE (user_id = %s 
               OR event_type = 'team_day' 
               OR (event_type = 'national_holiday' AND (
                   location_id = %s OR 
                   location_id IS NULL OR 
                   location_id = (SELECT id FROM locations WHERE name = 'Global' LIMIT 1)
               )))
              AND EXTRACT(YEAR FROM start_date) = %s
        """, (str(u_id), safe_loc_id, year))

        def is_active(y, w):
            if s_year and (y < s_year or (y == s_year and w < s_week)): return False
            if e_year and (y > e_year or (y == e_year and e_week and w > e_week)): return False
            return True

        time_off_per_week = {}  # Track days off specifically per week for math

        for e_type, e_start, e_end in cursor.fetchall():
            actual_days_off = 0
            d = e_start

            while d <= e_end:
                iso = d.isocalendar()
                if iso[0] == year and is_active(iso[0], iso[1]) and d.weekday() < 5:
                    actual_days_off += 1
                    time_off_per_week[iso[1]] = time_off_per_week.get(iso[1], 0) + 1
                d += timedelta(days=1)

            cost = actual_days_off * (base * 0.2)
            friendly_name = event_mapping.get(e_type, e_type)
            if friendly_name in events_cost:
                events_cost[friendly_name] += cost

        # --- Calculate Wasted Credits per User ---
        cursor.execute("""
            SELECT week_number, SUM(allocated_credits) 
            FROM assignments a 
            JOIN tests t ON a.test_id = t.id 
            WHERE a.user_id = %s AND a.year = %s AND t.stages::text != 'STOPPED' 
            GROUP BY week_number
        """, (str(u_id), year))
        user_assignments = {row[0]: float(row[1]) for row in cursor.fetchall()}

        u_wasted = 0.0
        for w in past_weeks:
            if is_active(year, w):
                prov = base - (time_off_per_week.get(w, 0) * (base * 0.2))
                used = user_assignments.get(w, 0.0)
                waste = max(0.0, prov - used)
                u_wasted += waste

        if u_wasted > 0:
            wasted_breakdown[u_name] = round(u_wasted, 1)
            total_wasted += u_wasted

    total_time_off = sum(events_cost.values())

    # ---  FORECAST BREAKDOWNS (ACTIVE SERVICES ONLY) ---
    # Scheduled (Assigned)
    cursor.execute("""
        SELECT sl.name, SUM(a.allocated_credits) 
        FROM assignments a 
        JOIN tests t ON a.test_id = t.id 
        JOIN services_lanes sl ON t.service_lane_id = sl.id 
        WHERE a.year = %s AND sl.is_active = TRUE AND t.stages::text != 'STOPPED'
        GROUP BY sl.name
    """, (year,))
    scheduled_breakdown = {row[0]: float(row[1]) for row in cursor.fetchall()}
    total_scheduled = sum(scheduled_breakdown.values())

    # Scheduled (Unassigned - missing pentesters)
    cursor.execute("""
        SELECT sl.name, SUM(t.credits_per_week * t.duration_weeks)
        FROM tests t
        JOIN services_lanes sl ON t.service_lane_id = sl.id
        WHERE t.start_year = %s 
          AND t.stages::text IN ('SCHEDULED', 'IN_PROGRESS') 
          AND sl.is_active = TRUE
          AND NOT EXISTS (
              SELECT 1 FROM assignments a WHERE a.test_id = t.id AND a.year = %s
          )
        GROUP BY sl.name
    """, (year, year))
    unassigned_sched_breakdown = {row[0]: float(row[1]) for row in cursor.fetchall()}
    total_unassigned_sched = sum(unassigned_sched_breakdown.values())

    # Placeholders
    cursor.execute("""
            SELECT SUM(sp.credits)
            FROM service_placeholders sp
            JOIN services_lanes sl ON sp.service_lane_id = sl.id
            WHERE sp.year = %s AND sl.is_active = TRUE
        """, (year,))

    ph_sum = cursor.fetchone()[0]
    total_placeholders = float(ph_sum or 0.0)

    if total_placeholders > 0:
        # This adds the line item to the UI card
        unassigned_sched_breakdown["Placeholders (All Lanes)"] = total_placeholders
        # This deducts it from your net capacity and bench math
        # total_unassigned_sched += total_placeholders

    # Backlog
    cursor.execute("""
        SELECT sl.name, SUM(t.credits_per_week * t.duration_weeks) 
        FROM tests t 
        JOIN services_lanes sl ON t.service_lane_id = sl.id 
        WHERE t.stages::text = 'NOT_PLANNED' AND sl.is_active = TRUE
        GROUP BY sl.name
    """)
    backlog_breakdown = {row[0]: float(row[1]) for row in cursor.fetchall()}
    total_backlog = sum(backlog_breakdown.values())

    # ---  TARGET VS ACTUAL (ALL SERVICES & CATEGORIES) ---
    cursor.execute("""
        SELECT sl.id, sl.name, COALESCE(slg.target_goal, 0) as target_goal, sl.theme_color, sl.is_active
        FROM services_lanes sl
        LEFT JOIN service_lane_goals slg ON sl.id = slg.service_lane_id AND slg.year = %s
        ORDER BY sl.display_order ASC, sl.name ASC
    """, (year,))
    services_data = []

    for s_id, s_name, s_goal, s_color, s_active in cursor.fetchall():
        s_dict = {
            "id": str(s_id), "name": s_name, "target_goal": s_goal or 0,
            "theme_color": s_color, "is_active": s_active, "categories": []
        }

        # Overall Service Counts & Theoretical Credits
        cursor.execute("""
            SELECT 
                COUNT(DISTINCT CASE WHEN stages::text = 'NOT_PLANNED' THEN id END),
                COUNT(DISTINCT CASE WHEN stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND start_year = %s THEN id END),
                COUNT(DISTINCT CASE WHEN stages::text = 'COMPLETED' AND start_year = %s THEN id END),
                COALESCE(SUM(CASE 
                    WHEN stages::text = 'NOT_PLANNED' THEN (credits_per_week * duration_weeks)
                    WHEN stages::text IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED') AND start_year = %s THEN (credits_per_week * duration_weeks)
                    ELSE 0 
                END), 0)
            FROM tests WHERE service_lane_id = %s
        """, (year, year, year, str(s_id)))
        counts = cursor.fetchone()

        # Assigned Credits
        cursor.execute("""
            SELECT COALESCE(SUM(a.allocated_credits), 0)
            FROM assignments a
            JOIN tests t ON a.test_id = t.id
            WHERE t.service_lane_id = %s AND a.year = %s AND t.stages::text != 'STOPPED'
        """, (str(s_id), year))
        assigned_credits = cursor.fetchone()[0]

        s_dict.update({
            "unplanned": counts[0],
            "planned": counts[1],
            "completed": counts[2],
            "theoretical_credits": float(counts[3]),
            "assigned_credits": float(assigned_credits)
        })

        # Categories - Using CTEs to prevent JOIN duplication inflation
        cursor.execute("""
            SELECT c.id, c.name, COALESCE(cg.target_goal, 0) as target_goal 
            FROM service_categories c
            LEFT JOIN service_category_goals cg ON c.id = cg.category_id AND cg.year = %s
            WHERE c.service_lane_id = %s
        """, (year, str(s_id)))
        cats = cursor.fetchall()
        cat_sum_goals = 0

        if cats:
            for c_id, c_name, c_goal in cats:
                cat_sum_goals += (c_goal or 0)

                cursor.execute("""
                    WITH CategoryTests AS (
                        SELECT DISTINCT t.id, t.stages, t.start_year, t.credits_per_week, t.duration_weeks
                        FROM tests t
                        LEFT JOIN test_assets ta ON t.id = ta.test_id
                        LEFT JOIN assets a ON ta.asset_id = a.id
                        LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
                        WHERE t.service_lane_id = %s AND ra.category_id = %s
                    )
                    SELECT 
                        COUNT(CASE WHEN stages::text = 'NOT_PLANNED' THEN id END),
                        COUNT(CASE WHEN stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND start_year = %s THEN id END),
                        COUNT(CASE WHEN stages::text = 'COMPLETED' AND start_year = %s THEN id END),
                        COALESCE(SUM(CASE 
                            WHEN stages::text = 'NOT_PLANNED' THEN (credits_per_week * duration_weeks)
                            WHEN stages::text IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED') AND start_year = %s THEN (credits_per_week * duration_weeks)
                            ELSE 0 
                        END), 0)
                    FROM CategoryTests
                """, (str(s_id), str(c_id), year, year, year))
                c_counts = cursor.fetchone()

                cursor.execute("""
                    WITH CategoryTests AS (
                        SELECT DISTINCT t.id
                        FROM tests t
                        LEFT JOIN test_assets ta ON t.id = ta.test_id
                        LEFT JOIN assets a ON ta.asset_id = a.id
                        LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
                        WHERE t.service_lane_id = %s AND ra.category_id = %s AND t.stages::text != 'STOPPED'
                    )
                    SELECT COALESCE(SUM(a.allocated_credits), 0)
                    FROM assignments a
                    JOIN CategoryTests ct ON a.test_id = ct.id
                    WHERE a.year = %s
                """, (str(s_id), str(c_id), year))
                c_assigned = cursor.fetchone()[0]

                s_dict["categories"].append({
                    "id": str(c_id), "name": c_name, "target_goal": c_goal or 0,
                    "unplanned": c_counts[0] or 0, "planned": c_counts[1] or 0, "completed": c_counts[2] or 0,
                    "theoretical_credits": float(c_counts[3]), "assigned_credits": float(c_assigned)
                })

            # Ghost Category (Uncategorized)
            cursor.execute("""
                WITH CategoryTests AS (
                    SELECT DISTINCT t.id, t.stages, t.start_year, t.credits_per_week, t.duration_weeks
                    FROM tests t
                    LEFT JOIN test_assets ta ON t.id = ta.test_id
                    LEFT JOIN assets a ON ta.asset_id = a.id
                    LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
                    WHERE t.service_lane_id = %s AND ra.category_id IS NULL
                )
                SELECT 
                    COUNT(CASE WHEN stages::text = 'NOT_PLANNED' THEN id END),
                    COUNT(CASE WHEN stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND start_year = %s THEN id END),
                    COUNT(CASE WHEN stages::text = 'COMPLETED' AND start_year = %s THEN id END),
                    COALESCE(SUM(CASE 
                        WHEN stages::text = 'NOT_PLANNED' THEN (credits_per_week * duration_weeks)
                        WHEN stages::text IN ('SCHEDULED', 'IN_PROGRESS', 'COMPLETED') AND start_year = %s THEN (credits_per_week * duration_weeks)
                        ELSE 0 
                    END), 0)
                FROM CategoryTests
            """, (str(s_id), year, year, year))
            u_counts = cursor.fetchone()

            if sum(u_counts[:3]) > 0:
                cursor.execute("""
                    WITH CategoryTests AS (
                        SELECT DISTINCT t.id
                        FROM tests t
                        LEFT JOIN test_assets ta ON t.id = ta.test_id
                        LEFT JOIN assets a ON ta.asset_id = a.id
                        LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
                        WHERE t.service_lane_id = %s AND ra.category_id IS NULL AND t.stages::text != 'STOPPED'
                    )
                    SELECT COALESCE(SUM(a.allocated_credits), 0)
                    FROM assignments a
                    JOIN CategoryTests ct ON a.test_id = ct.id
                    WHERE a.year = %s
                """, (str(s_id), year))
                u_assigned = cursor.fetchone()[0]

                s_dict["categories"].append({
                    "id": "uncategorized", "name": "Uncategorized", "target_goal": 0,
                    "unplanned": u_counts[0] or 0, "planned": u_counts[1] or 0, "completed": u_counts[2] or 0,
                    "theoretical_credits": float(u_counts[3]), "assigned_credits": float(u_assigned)
                })

        s_dict["goal_warning"] = (s_goal or 0) < cat_sum_goals
        services_data.append(s_dict)

    return {
        "year": year,
        "header": {
            "gross_capacity": total_gross_credits,
            "total_time_off": total_time_off,
            "assigned_resources": total_scheduled,
            "unassigned_bench": max(0.0, total_gross_credits - total_time_off - total_scheduled - total_wasted)
        },
        "forecast": {
            "scheduled": {"total": total_scheduled, "breakdown": scheduled_breakdown},
            "unassigned_scheduled": {"total": total_unassigned_sched, "breakdown": unassigned_sched_breakdown},
            "backlog": {"total": total_backlog, "breakdown": backlog_breakdown},
            "time_off": {"total": total_time_off, "breakdown": events_cost},
            "wasted": {"total": total_wasted, "breakdown": wasted_breakdown},
            "net_capacity": total_gross_credits - (
                        total_scheduled + total_unassigned_sched + total_backlog + total_time_off + total_wasted)
        },
        "services": services_data
    }