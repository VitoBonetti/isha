from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func, case, or_, and_
from models.tests import Tests, TestStages, Assignments, TestAssets
from models.users import Users
from models.events import Events
from models.territories import Locations
from models.services import ServiceLanes, ServiceCategories, ServiceCategoryGoals, ServiceLaneGoals, ServicePlaceholders
from models.assets import Assets
from models.raw_assets import RawAssets


def get_available_years(db: Session):
    """Fetches the distinct list of years that have scheduled tests."""
    years = (db.query(Tests.start_year)
             .filter(Tests.start_year.isnot(None))
             .distinct()
             .order_by(Tests.start_year.desc()).all())

    if not years:
        return [datetime.now().year]
    return [r[0] for r in years]


def get_yearly_insights(db: Session, year: int):
    """Calculates gross capacity, time off, wasted credits, and forecast breakdowns."""
    if not year:
        year = datetime.now().year

    # --- DETERMINE PAST WEEKS FOR "WASTED" MATH ---
    current_year_real = datetime.now().year
    current_week_real = datetime.now().isocalendar()[1]

    past_weeks = []
    if year < current_year_real:
        d = datetime(year, 12, 28)
        max_w = d.isocalendar()[1]
        past_weeks = list(range(1, max_w + 1))
    elif year == current_year_real:
        past_weeks = list(range(1, current_week_real))

    # --- GROSS CAPACITY, TIME OFF & WASTED ---
    users = db.query(Users).all()

    total_gross_credits = 0.0
    events_cost = {"National Holiday": 0.0, "Team Day": 0.0, "Personal Time Off": 0.0, "Sick Day": 0.0}
    event_mapping = {"national_holiday": "National Holiday", "team_day": "Team Day",
                     "personal_time_off": "Personal Time Off", "sick_day": "Sick Day"}

    wasted_breakdown = {}
    total_wasted = 0.0
    total_weeks_in_year = datetime(year, 12, 28).isocalendar()[1]

    global_loc = db.query(Locations).filter(Locations.name == 'Global').first()
    global_loc_id = str(global_loc.id) if global_loc else None

    for user in users:
        base = float(user.base_capacity or 0.0)
        s_year, s_week = user.start_year, user.start_week
        e_year, e_week = user.end_year, user.end_week

        start = s_week if s_year == year else 1
        end = e_week if e_year == year else total_weeks_in_year
        if (s_year and year < s_year) or (e_year and year > e_year): continue

        active_weeks = max(0, end - start + 1)
        total_gross_credits += (active_weeks * base)

        safe_loc_id = str(user.location_id) if user.location_id else None

        # Fetch Events
        user_events = db.query(Events).filter(
            func.extract('YEAR', Events.start_date) == year,
            or_(
                Events.user_id == str(user.id),
                Events.event_type == 'team_day',
                and_(
                    Events.event_type == 'national_holiday',
                    or_(
                        Events.location_id == safe_loc_id,
                        Events.location_id.is_(None),
                        Events.location_id == global_loc_id
                    )
                )
            )
        ).all()

        def is_active(y, w):
            if s_year and (y < s_year or (y == s_year and w < s_week)): return False
            if e_year and (y > e_year or (y == e_year and e_week and w > e_week)): return False
            return True

        time_off_per_week = {}

        for event in user_events:
            if not event.start_date or not event.end_date: continue

            actual_days_off = 0
            d = event.start_date

            while d <= event.end_date:
                iso = d.isocalendar()
                if iso[0] == year and is_active(iso[0], iso[1]) and d.weekday() < 5:
                    actual_days_off += 1
                    time_off_per_week[iso[1]] = time_off_per_week.get(iso[1], 0) + 1
                d += timedelta(days=1)

            cost = actual_days_off * (base * 0.2)
            friendly_name = event_mapping.get(event.event_type, event.event_type)
            if friendly_name in events_cost:
                events_cost[friendly_name] += cost

        # User Assignments
        assignments = (db.query(Assignments.week_number, func.sum(Assignments.allocated_credits))
                       .join(Tests, Assignments.test_id == Tests.id)
                       .filter(Assignments.user_id == str(user.id), Assignments.year == year, Tests.stages != TestStages.STOPPED)
                       .group_by(Assignments.week_number).all())

        user_assignments = {r[0]: float(r[1]) for r in assignments}

        u_wasted = 0.0
        for w in past_weeks:
            if is_active(year, w):
                prov = base - (time_off_per_week.get(w, 0) * (base * 0.2))
                used = user_assignments.get(w, 0.0)
                waste = max(0.0, prov - used)
                u_wasted += waste

        if u_wasted > 0:
            wasted_breakdown[user.name] = round(u_wasted, 1)
            total_wasted += u_wasted

    total_time_off = sum(events_cost.values())

    # --- FORECAST BREAKDOWNS ---
    sched_breakdown = (db.query(ServiceLanes.name, func.sum(Assignments.allocated_credits))
                       .join(Tests, Assignments.test_id == Tests.id)
                       .join(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                       .filter(Assignments.year == year, ServiceLanes.is_active == True, Tests.stages != TestStages.STOPPED)
                       .group_by(ServiceLanes.name).all())

    scheduled_breakdown = {r[0]: float(r[1]) for r in sched_breakdown}
    total_scheduled = sum(scheduled_breakdown.values())

    # Unassigned Scheduled Tests
    has_assignment_subq = (db.query(Assignments.id)
                           .filter(Assignments.test_id == Tests.id, Assignments.year == year)
                           .correlate(Tests).exists())

    unassigned_breakdown = (db.query(ServiceLanes.name, func.sum(Tests.credits_per_week * Tests.duration_weeks))
                            .join(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                            .filter(Tests.start_year == year,
                                    Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS]),
                                    ServiceLanes.is_active == True,
                                    ~has_assignment_subq)
                            .group_by(ServiceLanes.name).all())

    unassigned_sched_breakdown = {r[0]: float(r[1]) for r in unassigned_breakdown}
    total_unassigned_sched = sum(unassigned_sched_breakdown.values())

    # Placeholders
    ph_sum = (db.query(func.sum(ServicePlaceholders.credits))
              .join(ServiceLanes, ServicePlaceholders.service_lane_id == ServiceLanes.id)
              .filter(ServicePlaceholders.year == year, ServiceLanes.is_active == True).scalar())

    total_placeholders = float(ph_sum or 0.0)
    if total_placeholders > 0:
        unassigned_sched_breakdown["Placeholders (All Lanes)"] = total_placeholders

    # Backlog Breakdown
    backlog_bdown = (db.query(ServiceLanes.name, func.sum(Tests.credits_per_week * Tests.duration_weeks))
                     .join(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
                     .filter(Tests.stages == TestStages.NOT_PLANNED, ServiceLanes.is_active == True)
                     .group_by(ServiceLanes.name).all())

    backlog_breakdown = {r[0]: float(r[1]) for r in backlog_bdown}
    total_backlog = sum(backlog_breakdown.values())

    # --- TARGET VS ACTUAL ---
    services = (db.query(ServiceLanes, ServiceLaneGoals.target_goal)
                .outerjoin(ServiceLaneGoals, and_(ServiceLanes.id == ServiceLaneGoals.service_lane_id, ServiceLaneGoals.year == year))
                .order_by(ServiceLanes.display_order.asc(), ServiceLanes.name.asc()).all())

    services_data = []

    for s, target_goal in services:
        s_id_str = str(s.id)
        s_dict = {
            "id": s_id_str, "name": s.name, "target_goal": target_goal or 0,
            "theme_color": s.theme_color, "is_active": s.is_active, "categories": []
        }

        counts = db.query(
            func.count(func.distinct(case((Tests.stages == TestStages.NOT_PLANNED, Tests.id)))),
            func.count(func.distinct(case(
                (and_(Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS]), Tests.start_year == year),
                 Tests.id)))),
            func.count(
                func.distinct(case((and_(Tests.stages == TestStages.COMPLETED, Tests.start_year == year), Tests.id)))),
            func.coalesce(func.sum(case(
                (Tests.stages == TestStages.NOT_PLANNED, Tests.credits_per_week * Tests.duration_weeks),
                (and_(Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS, TestStages.COMPLETED]),
                      Tests.start_year == year), Tests.credits_per_week * Tests.duration_weeks),
                else_=0
            )), 0)
        ).filter(Tests.service_lane_id == s_id_str).first()

        assigned_credits = (db.query(func.coalesce(func.sum(Assignments.allocated_credits), 0))
                            .join(Tests, Assignments.test_id == Tests.id)
                            .filter(Tests.service_lane_id == s_id_str,
                                    Assignments.year == year,
                                    Tests.stages != TestStages.STOPPED)
                            .scalar())

        s_dict.update({
            "unplanned": counts[0],
            "planned": counts[1],
            "completed": counts[2],
            "theoretical_credits": float(counts[3]),
            "assigned_credits": float(assigned_credits)
        })

        # Category Breakdown
        cats = (db.query(ServiceCategories, ServiceCategoryGoals.target_goal)
                .outerjoin(ServiceCategoryGoals,
                           and_(ServiceCategories.id == ServiceCategoryGoals.category_id,
                                ServiceCategoryGoals.year == year))
                .filter(ServiceCategories.service_lane_id == s_id_str).all())

        cat_sum_goals = 0

        # ONLY run category and uncategorized math if this lane actually HAS categories!
        if cats:
            cat_sum_goals = sum((cg or 0) for _, cg in cats)

            for cat, c_goal in cats:
                # 1. Create the deduplicated subquery explicitly
                c_subq = (db.query(
                    Tests.id, Tests.stages, Tests.start_year, Tests.credits_per_week, Tests.duration_weeks)
                          .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
                          .outerjoin(Assets, TestAssets.asset_id == Assets.id)
                          .outerjoin(RawAssets, Assets.raw_asset_id == RawAssets.id)
                          .filter(Tests.service_lane_id == s_id_str, RawAssets.category_id == str(cat.id))
                          .distinct().subquery())

                # 2. Reference the subquery's columns (.c) in the outer query
                c_counts = db.query(
                    func.count(case((c_subq.c.stages == TestStages.NOT_PLANNED, c_subq.c.id))),
                    func.count(case((and_(c_subq.c.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS]),
                                          c_subq.c.start_year == year), c_subq.c.id))),
                    func.count(case(
                        (and_(c_subq.c.stages == TestStages.COMPLETED, c_subq.c.start_year == year), c_subq.c.id))),
                    func.coalesce(func.sum(case(
                        (c_subq.c.stages == TestStages.NOT_PLANNED,
                         c_subq.c.credits_per_week * c_subq.c.duration_weeks),
                        (and_(c_subq.c.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS, TestStages.COMPLETED]),
                              c_subq.c.start_year == year), c_subq.c.credits_per_week * c_subq.c.duration_weeks),
                        else_=0
                    )), 0)
                ).first()

                c_assigned = (db.query(func.coalesce(func.sum(Assignments.allocated_credits), 0))
                              .join(c_subq, Assignments.test_id == c_subq.c.id)
                              .filter(Assignments.year == year, c_subq.c.stages != TestStages.STOPPED).scalar())

                s_dict["categories"].append({
                    "id": str(cat.id), "name": cat.name, "target_goal": c_goal or 0,
                    "unplanned": c_counts[0] or 0, "planned": c_counts[1] or 0, "completed": c_counts[2] or 0,
                    "theoretical_credits": float(c_counts[3]), "assigned_credits": float(c_assigned)
                })

            # --- Uncategorized Logic (Now safely indented!) ---
            u_subq = (db.query(
                Tests.id, Tests.stages, Tests.start_year, Tests.credits_per_week, Tests.duration_weeks)
                      .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
                      .outerjoin(Assets, TestAssets.asset_id == Assets.id)
                      .outerjoin(RawAssets, Assets.raw_asset_id == RawAssets.id)
                      .filter(Tests.service_lane_id == s_id_str, RawAssets.category_id.is_(None))
                      .distinct().subquery())

            u_counts = db.query(
                func.count(case((u_subq.c.stages == TestStages.NOT_PLANNED, u_subq.c.id))),
                func.count(case((and_(u_subq.c.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS]),
                                      u_subq.c.start_year == year), u_subq.c.id))),
                func.count(
                    case((and_(u_subq.c.stages == TestStages.COMPLETED, u_subq.c.start_year == year), u_subq.c.id))),
                func.coalesce(func.sum(case(
                    (u_subq.c.stages == TestStages.NOT_PLANNED, u_subq.c.credits_per_week * u_subq.c.duration_weeks),
                    (and_(u_subq.c.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS, TestStages.COMPLETED]),
                          u_subq.c.start_year == year), u_subq.c.credits_per_week * u_subq.c.duration_weeks),
                    else_=0
                )), 0)
            ).first()

            if sum(u_counts[:3]) > 0:
                u_assigned = (db.query(func.coalesce(func.sum(Assignments.allocated_credits), 0))
                              .join(u_subq, Assignments.test_id == u_subq.c.id)
                              .filter(Assignments.year == year, u_subq.c.stages != TestStages.STOPPED).scalar())

                s_dict["categories"].append({
                    "id": "uncategorized", "name": "Uncategorized", "target_goal": 0,
                    "unplanned": u_counts[0] or 0, "planned": u_counts[1] or 0, "completed": u_counts[2] or 0,
                    "theoretical_credits": float(u_counts[3]), "assigned_credits": float(u_assigned)
                })

        s_dict["goal_warning"] = (target_goal or 0) < cat_sum_goals
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