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

    # ---  GROSS CAPACITY & TIME OFF ---
    cursor.execute("SELECT id, base_capacity, start_year, start_week, end_year, end_week, location_id FROM users")
    users = cursor.fetchall()

    total_gross_credits = 0.0
    events_cost = {"National Holiday": 0.0, "Team Day": 0.0, "Personal Time Off": 0.0, "Sick Day": 0.0}
    event_mapping = {"national_holiday": "National Holiday", "team_day": "Team Day",
                     "personal_time_off": "Personal Time Off", "sick_day": "Sick Day"}

    for u_id, base_cap, s_year, s_week, e_year, e_week, loc_id in users:
        base = float(base_cap or 0.0)
        start = s_week if s_year == year else 1
        end = e_week if e_year == year else 52
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

        for e_type, e_start, e_end in cursor.fetchall():
            actual_days_off = 0
            d = e_start

            # Check day-by-day to ensure the event falls inside the user's active tenure
            while d <= e_end:
                iso = d.isocalendar()
                if is_active(iso[0], iso[1]) and d.weekday() < 5:  # Weekdays only
                    actual_days_off += 1
                d += timedelta(days=1)

            cost = actual_days_off * (base * 0.2)
            friendly_name = event_mapping.get(e_type, e_type)
            if friendly_name in events_cost:
                events_cost[friendly_name] += cost

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
        total_unassigned_sched += total_placeholders

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
        SELECT id, name, target_goal, theme_color, is_active
        FROM services_lanes ORDER BY display_order ASC, name ASC
    """)
    services_data = []

    for s_id, s_name, s_goal, s_color, s_active in cursor.fetchall():
        s_dict = {
            "id": str(s_id), "name": s_name, "target_goal": s_goal or 0,
            "theme_color": s_color, "is_active": s_active, "categories": []
        }

        # Overall Service Counts
        cursor.execute("""
                SELECT 
                    COUNT(DISTINCT CASE WHEN stages::text = 'NOT_PLANNED' THEN id END),
                    COUNT(DISTINCT CASE WHEN stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND start_year = %s THEN id END),
                    COUNT(DISTINCT CASE WHEN stages::text = 'COMPLETED' AND start_year = %s THEN id END)
                FROM tests WHERE service_lane_id = %s
            """, (year, year, str(s_id)))
        counts = cursor.fetchone()
        s_dict.update({"unplanned": counts[0], "planned": counts[1], "completed": counts[2]})

        # Categories
        cursor.execute("SELECT id, name, target_goal FROM service_categories WHERE service_lane_id = %s", (str(s_id),))
        cats = cursor.fetchall()
        cat_sum_goals = 0

        if cats:
            for c_id, c_name, c_goal in cats:
                cat_sum_goals += (c_goal or 0)
                # Correctly join through assets to find the test's category
                cursor.execute("""
                        SELECT 
                            COUNT(DISTINCT CASE WHEN t.stages::text = 'NOT_PLANNED' THEN t.id END),
                            COUNT(DISTINCT CASE WHEN t.stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND t.start_year = %s THEN t.id END),
                            COUNT(DISTINCT CASE WHEN t.stages::text = 'COMPLETED' AND t.start_year = %s THEN t.id END)
                        FROM tests t
                        LEFT JOIN test_assets ta ON t.id = ta.test_id
                        LEFT JOIN assets a ON ta.asset_id = a.id
                        LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
                        WHERE t.service_lane_id = %s AND ra.category_id = %s
                    """, (year, year, str(s_id), str(c_id)))
                c_counts = cursor.fetchone()
                s_dict["categories"].append({
                    "id": str(c_id), "name": c_name, "target_goal": c_goal or 0,
                    "unplanned": c_counts[0] or 0, "planned": c_counts[1] or 0, "completed": c_counts[2] or 0
                })

            # Ghost Category (Uncategorized) - ONLY show if there are other real categories
            cursor.execute("""
                    SELECT 
                        COUNT(DISTINCT CASE WHEN t.stages::text = 'NOT_PLANNED' THEN t.id END),
                        COUNT(DISTINCT CASE WHEN t.stages::text IN ('SCHEDULED', 'IN_PROGRESS') AND t.start_year = %s THEN t.id END),
                        COUNT(DISTINCT CASE WHEN t.stages::text = 'COMPLETED' AND t.start_year = %s THEN t.id END)
                    FROM tests t
                    LEFT JOIN test_assets ta ON t.id = ta.test_id
                    LEFT JOIN assets a ON ta.asset_id = a.id
                    LEFT JOIN raw_assets ra ON a.raw_asset_id = ra.id
                    WHERE t.service_lane_id = %s AND ra.category_id IS NULL
                """, (year, year, str(s_id)))
            u_counts = cursor.fetchone()
            if sum(u_counts) > 0:
                s_dict["categories"].append({
                    "id": "uncategorized", "name": "Uncategorized", "target_goal": 0,
                    "unplanned": u_counts[0] or 0, "planned": u_counts[1] or 0, "completed": u_counts[2] or 0
                })

        s_dict["goal_warning"] = (s_goal or 0) < cat_sum_goals
        services_data.append(s_dict)

    return {
        "year": year,
        "header": {
            "gross_capacity": total_gross_credits,
            "total_time_off": total_time_off,
            "assigned_resources": total_scheduled,
            "unassigned_bench": max(0.0, total_gross_credits - total_time_off - total_scheduled)
        },
        "forecast": {
            "scheduled": {"total": total_scheduled, "breakdown": scheduled_breakdown},
            "unassigned_scheduled": {"total": total_unassigned_sched, "breakdown": unassigned_sched_breakdown},
            "backlog": {"total": total_backlog, "breakdown": backlog_breakdown},
            "time_off": {"total": total_time_off, "breakdown": events_cost},
            "net_capacity": total_gross_credits - (total_scheduled + total_unassigned_sched + total_backlog + total_time_off)
        },
        "services": services_data
    }