import uuid
from datetime import datetime, timedelta
from fastapi import HTTPException
from starlette import status
from sqlalchemy.orm import Session
from sqlalchemy import func, or_, and_, cast, String
from sqlalchemy.exc import IntegrityError
from models.users import Users
from models.events import Events
from models.territories import Locations
from models.tests import Tests, TestStages, Assignments, TestAssets
from models.secret_notes import SecretNotes
from models.services import ServiceLanes, ServiceCategories, ServiceCategoryGoals, ServicePlaceholders
from models.notifications import Notifications
from audit_logger import log_audit_event


# --- CAPACITY & SCHEDULING ENGINE ---
def get_user_provision_internal(db: Session, user_id, year, week_number):
    """Fallback single-user capacity lookup for rebalancing routines."""
    user = db.query(Users).filter(Users.id == user_id).first()
    if not user: return 0.0
    base_cap = float(user.base_capacity or 0.0)
    start_week = user.start_week if user.start_week is not None else 1
    start_year = user.start_year if user.start_year is not None else 2024
    end_week = user.end_week
    end_year = user.end_year

    if year < start_year: return 0.0
    if year == start_year and week_number < start_week: return 0.0
    if end_year and year > end_year: return 0.0
    if end_year and year == end_year and end_week and week_number > end_week: return 0.0

    safe_loc_id = str(user.location_id) if user.location_id is not None else None
    global_loc = db.query(Locations.id).filter(Locations.name == 'Global').first()
    global_loc_id = str(global_loc[0]) if global_loc else None

    events = db.query(Events).filter(
        or_(
            and_(Events.user_id == user_id, Events.event_type != 'working_from_abroad'),
            Events.event_type == 'team_day',
            and_(
                Events.event_type == 'national_holiday',
                or_(
                    Events.location_id == safe_loc_id,
                    Events.location_id == None,
                    Events.location_id == global_loc_id
                )
            )
        )
    ).all()

    week_dates = []
    for day in range(1, 6):
        try:
            week_dates.append(datetime.strptime(f"{year}-W{week_number}-{day}", "%G-W%V-%u").strftime('%Y-%m-%d'))
        except ValueError:
            continue

    days_off = 0
    for e in events:
        if not e.start_date or not e.end_date: continue
        event_dates = [(e.start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((e.end_date - e.start_date).days + 1)]
        days_off += sum(1 for w in week_dates if w in event_dates)

    return max(0.0, base_cap - (days_off * 0.2))


def get_quarter_weeks(q: int, year: int):
    if q == 1: return range(1, 14)
    if q == 2: return range(14, 27)
    if q == 3: return range(27, 40)
    last_week = datetime(year, 12, 28).isocalendar()[1]
    return range(40, last_week + 1)


def calculate_weekly_capacity(db: Session, user_id: str, year: int, week_number: int):
    provision = get_user_provision_internal(db, user_id, year, week_number)
    used = (db.query(func.sum(Assignments.allocated_credits)).join(Tests, Assignments.test_id == Tests.id)
            .filter(Assignments.user_id == user_id,
                    Assignments.year == year,
                    Assignments.week_number == week_number,
                    cast(Tests.stages, String) != 'Unable'
            ).scalar() or 0.0)
    return max(0.0, round(provision - used, 1))


def rebalance_user_week_assignments(db: Session, user_id: str, year: int, week_number: int):
    provision = get_user_provision_internal(db, user_id, year, week_number)
    assignments = db.query(Assignments, Tests.name.label("test_name")) \
        .join(Tests, Assignments.test_id == Tests.id) \
        .filter(Assignments.user_id == user_id, Assignments.year == year, Assignments.week_number == week_number) \
        .order_by(Assignments.allocated_credits.desc()).all()
    if not assignments: return
    total_used = sum(a.Assignments.allocated_credits for a in assignments)
    if total_used > provision:
        excess = total_used - provision
        for asg, t_name in assignments:
            if excess <= 0: break
            reduction = min(asg.allocated_credits, excess)
            new_alloc = round(asg.allocated_credits - reduction, 1)
            excess -= reduction
            if new_alloc > 0:
                asg.allocated_credits = new_alloc
                msg = f"Your capacity on '{t_name}' (Wk {week_number}) was reduced to {new_alloc}cr due to time off."
                db.add(Notifications(user_id=user_id, message=msg, type="WARNING"))
            else:
                db.delete(asg)
                msg = f"You were removed from '{t_name}' (Wk {week_number}) due to time off."
                db.add(Notifications(user_id=user_id, message=msg, type="REMOVAL"))
        db.commit()


def rebalance_affected_assignments(db: Session, start_date, end_date, user_id=None, location_id=None):
    if not start_date or not end_date: return
    affected_weeks = set()
    d = start_date
    while d <= end_date:
        iso = d.isocalendar()
        affected_weeks.add((iso[0], iso[1]))
        d += timedelta(days=1)
    users_to_rebalance = []
    if user_id:
        users_to_rebalance = [str(user_id)]
    else:
        query = db.query(Users.id)
        if location_id:
            query = query.filter(Users.location_id == location_id)
        users_to_rebalance = [str(r[0]) for r in query.all()]
    for u in users_to_rebalance:
        for y, w in affected_weeks:
            rebalance_user_week_assignments(db, u, y, w)


# --- MAIN BOARD PAYLOAD (BULK-OPTIMIZED) ---
def get_quarterly_board(db: Session, year: int, quarter: int, current_user: dict):
    weeks = list(get_quarter_weeks(quarter, year))
    weeks_in_prev_year = datetime(year - 1, 12, 28).isocalendar()[1]
    user_role = current_user.get('role')
    lane_id = current_user.get('service_lane_id')

    # 1. Services
    services_query = db.query(ServiceLanes).order_by(ServiceLanes.display_order.asc())
    services = [{
        "id": str(s.id), "name": s.name, "theme_color": s.theme_color,
        "max_concurrent_per_week": s.max_concurrent_per_week, "is_active": s.is_active,
        "auto_provision_workspace": s.auto_provision_workspace
    } for s in services_query.all()]

    # 2. Categories & Goals
    cats_query = db.query(ServiceCategories, ServiceCategoryGoals.target_goal) \
        .outerjoin(ServiceCategoryGoals,
                   and_(ServiceCategories.id == ServiceCategoryGoals.category_id, ServiceCategoryGoals.year == year)) \
        .order_by(ServiceCategories.name.asc())
    categories = [{
        "id": str(c.ServiceCategories.id), "name": c.ServiceCategories.name,
        "target_goal": c.target_goal or 0,
        "service_lane_id": str(c.ServiceCategories.service_lane_id) if c.ServiceCategories.service_lane_id else None
    } for c in cats_query.all()]

    # 3. Pentesters
    users = db.query(Users).all()
    pentesters = [{
        "id": str(u.id), "name": u.name, "role": u.role, "email": u.email,
        "capacity": u.base_capacity, "location_id": str(u.location_id) if u.location_id else None,
        "start_week": u.start_week, "start_year": u.start_year, "end_week": u.end_week, "end_year": u.end_year
    } for u in users]

    extended_week_pairs = [(year, w) for w in weeks]
    prev_y, prev_w = year, weeks[0]
    for _ in range(4):
        prev_w -= 1
        if prev_w < 1:
            prev_y -= 1
            prev_w = datetime(prev_y, 12, 28).isocalendar()[1]
        extended_week_pairs.append((prev_y, prev_w))

    next_y, next_w = year, weeks[-1]
    for _ in range(8):
        next_w += 1
        max_w = datetime(next_y, 12, 28).isocalendar()[1]
        if next_w > max_w:
            next_y += 1
            next_w = 1
        extended_week_pairs.append((next_y, next_w))

    # --- BULK CAPACITY COMPUTATION ---
    global_loc = db.query(Locations.id).filter(Locations.name == 'Global').first()
    global_loc_id = str(global_loc[0]) if global_loc else None
    pentester_ids = [p["id"] for p in pentesters]

    all_events = db.query(Events).filter(
        or_(
            Events.user_id.in_(pentester_ids),
            Events.event_type == 'team_day',
            and_(
                Events.event_type == 'national_holiday',
                or_(
                    Events.location_id.in_([p["location_id"] for p in pentesters if p["location_id"]]),
                    Events.location_id.is_(None),
                    Events.location_id == global_loc_id
                )
            )
        )
    ).all()

    unique_years = list(set(y for y, w in extended_week_pairs))
    unique_weeks = list(set(w for y, w in extended_week_pairs))

    asg_summary = (
        db.query(
            Assignments.user_id,
            Assignments.year,
            Assignments.week_number,
            func.sum(Assignments.allocated_credits).label("total_credits")
        )
        .join(Tests, Assignments.test_id == Tests.id)
        .filter(
            Assignments.user_id.in_(pentester_ids),
            Assignments.year.in_(unique_years),
            Assignments.week_number.in_(unique_weeks),
            cast(Tests.stages, String) != 'Unable'
        )
        .group_by(Assignments.user_id, Assignments.year, Assignments.week_number)
        .all()
    )

    asg_map = {
        (str(r.user_id), int(r.year), int(r.week_number)): float(r.total_credits or 0.0)
        for r in asg_summary
    }

    def compute_in_memory_provision(u_dict, year, week_number, events_list):
        base_cap = float(u_dict["capacity"] or 0.0)
        s_week = u_dict["start_week"] if u_dict["start_week"] is not None else 1
        s_year = u_dict["start_year"] if u_dict["start_year"] is not None else 2024
        e_week = u_dict["end_week"]
        e_year = u_dict["end_year"]

        if year < s_year: return 0.0
        if year == s_year and week_number < s_week: return 0.0
        if e_year and year > e_year: return 0.0
        if e_year and year == e_year and e_week and week_number > e_week: return 0.0

        safe_loc_id = u_dict["location_id"]
        week_dates = []
        for day in range(1, 6):
            try:
                week_dates.append(datetime.strptime(f"{year}-W{week_number}-{day}", "%G-W%V-%u").strftime('%Y-%m-%d'))
            except ValueError:
                continue

        days_off = 0
        for e in events_list:
            if not e.start_date or not e.end_date: continue
            e_user_id = str(e.user_id) if e.user_id else None
            e_loc_id = str(e.location_id) if e.location_id else None

            is_match = False
            if e.event_type != 'working_from_abroad' and e_user_id == u_dict["id"]:
                is_match = True
            elif e.event_type == 'team_day':
                is_match = True
            elif e.event_type == 'national_holiday':
                if e_loc_id == safe_loc_id or e_loc_id is None or e_loc_id == global_loc_id:
                    is_match = True

            if is_match:
                event_dates = [(e.start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in range((e.end_date - e.start_date).days + 1)]
                days_off += sum(1 for w in week_dates if w in event_dates)

        return max(0.0, base_cap - (days_off * 0.2))

    cap_matrix = {p["id"]: {} for p in pentesters}
    for p in pentesters:
        for y, w in extended_week_pairs:
            prov = compute_in_memory_provision(p, y, w, all_events)
            used = asg_map.get((p["id"], y, w), 0.0)
            cap_matrix[p["id"]][w] = max(0.0, round(prov - used, 1))

    enum_map = {"NOT_PLANNED": "Not Planned", "SCHEDULED": "Scheduled", "IN_PROGRESS": "In Progress",
                "STOPPED": "Stopped", "DELETED": "Deleted", "COMPLETED": "Completed", "ARCHIVED": "Archived"}

    def apply_maintainer_filter(query):
        if user_role == 'maintainer':
            return query.filter(Tests.service_lane_id == str(lane_id)) if lane_id else query.filter(
                Tests.service_lane_id == '00000000-0000-0000-0000-000000000000')
        return query

    # 4. Backlog Tests
    asset_count_sub = db.query(func.count(TestAssets.asset_id)).filter(TestAssets.test_id == Tests.id).correlate(
        Tests).scalar_subquery()
    has_secret_sub = db.query(func.count(SecretNotes.test_id) > 0).filter(SecretNotes.test_id == Tests.id).correlate(
        Tests).scalar_subquery()
    backlog_q = db.query(Tests, asset_count_sub.label("asset_count"), has_secret_sub.label("has_secret")) \
        .filter(Tests.stages == TestStages.NOT_PLANNED)
    backlog_q = apply_maintainer_filter(backlog_q)
    backlog = [{
        "id": str(r.Tests.id), "name": r.Tests.name,
        "service_lane_id": str(r.Tests.service_lane_id) if r.Tests.service_lane_id else None,
        "category_id": str(r.Tests.category_id) if r.Tests.category_id else None, "credits": r.Tests.credits_per_week,
        "duration": r.Tests.duration_weeks, "status": enum_map.get(r.Tests.stages.name, r.Tests.stages.name),
        "asset_count": r.asset_count, "has_secret": r.has_secret, "drive_folder_url": r.Tests.drive_folder_url,
        "is_tentative": r.Tests.is_tentative, "kiss24": str(r.Tests.kiss24) if r.Tests.kiss24 else None
    } for r in backlog_q.all()]

    # 5. Scheduled Tests
    sched_q = db.query(Tests, asset_count_sub.label("asset_count"), has_secret_sub.label("has_secret")) \
        .filter(
        Tests.stages.in_([TestStages.SCHEDULED, TestStages.IN_PROGRESS, TestStages.STOPPED, TestStages.COMPLETED]),
        or_(
            and_(Tests.start_year == year, (Tests.start_week + Tests.duration_weeks - 1) >= weeks[0],
                 Tests.start_week <= weeks[-1]),
            and_(Tests.start_year == year - 1,
                 (Tests.start_week + Tests.duration_weeks - 1) - weeks_in_prev_year >= weeks[0])
        )
    )
    sched_q = apply_maintainer_filter(sched_q)
    scheduled = [{
        "id": str(r.Tests.id), "name": r.Tests.name,
        "service_lane_id": str(r.Tests.service_lane_id) if r.Tests.service_lane_id else None,
        "category_id": str(r.Tests.category_id) if r.Tests.category_id else None, "credits": r.Tests.credits_per_week,
        "duration": r.Tests.duration_weeks, "startWeek": r.Tests.start_week, "startYear": r.Tests.start_year,
        "status": enum_map.get(r.Tests.stages.name, r.Tests.stages.name), "asset_count": r.asset_count,
        "has_secret": r.has_secret, "drive_folder_url": r.Tests.drive_folder_url, "is_tentative": r.Tests.is_tentative,
        "kiss24": str(r.Tests.kiss24) if r.Tests.kiss24 else None
    } for r in sched_q.all()]

    # 6. Assignments
    asg_q = db.query(Assignments, Users.name.label("user_name")) \
        .join(Users, Assignments.user_id == Users.id) \
        .filter(Assignments.year == year, Assignments.week_number.in_(weeks))
    assignments = [{
        "test_id": str(a.Assignments.test_id), "user_id": str(a.Assignments.user_id),
        "week_number": a.Assignments.week_number,
        "user_name": a.user_name, "allocated_credits": a.Assignments.allocated_credits
    } for a in asg_q.all()]

    # 7. Events
    events_q = db.query(Events).all()
    events = [{
        "id": str(e.id), "user_id": str(e.user_id) if e.user_id else None, "type": e.event_type,
        "location_id": str(e.location_id) if e.location_id else None, "start": e.start_date, "end": e.end_date
    } for e in events_q]

    # 8. Placeholders
    ph_q = db.query(ServicePlaceholders).filter(ServicePlaceholders.year == year).all()
    placeholders = [{
        "id": str(p.id), "service_lane_id": str(p.service_lane_id), "year": p.year, "week": p.week, "credits": p.credits
    } for p in ph_q]

    return {
        "year": year, "quarter": quarter, "weeks": weeks, "services": services, "categories": categories,
        "pentesters": pentesters, "capacities": cap_matrix, "backlog": backlog, "scheduled": scheduled,
        "assignments": assignments, "events": events, "placeholders": placeholders
    }


# --- UNIVERSAL CATEGORIES ---
def get_categories(db: Session, year: str):
    query = db.query(ServiceCategories, ServiceCategoryGoals.target_goal, ServiceCategoryGoals.year,
                     ServiceLanes.name.label("service_lane_name")) \
        .outerjoin(ServiceCategoryGoals, ServiceCategories.id == ServiceCategoryGoals.category_id) \
        .outerjoin(ServiceLanes, ServiceCategories.service_lane_id == ServiceLanes.id)
    if year and year != 'All':
        query = query.filter(ServiceCategoryGoals.year == int(year))
    query = query.order_by(ServiceCategoryGoals.year.desc().nullslast(), ServiceCategories.name.asc())
    return [{
        "id": str(c.ServiceCategories.id), "name": c.ServiceCategories.name, "target_goal": c.target_goal or 0,
        "goal_year": c.year, "service_lane_id": str(c.ServiceCategories.service_lane_id),
        "service_lane_name": c.service_lane_name
    } for c in query.all()]


def create_category(db: Session, cat, year: int, current_user: dict):
    lane_id = str(cat.service_lane_id) if cat.service_lane_id else None
    category = db.query(ServiceCategories).filter(ServiceCategories.name == cat.name).first()
    if category:
        category.service_lane_id = lane_id
        cat_id = str(category.id)
    else:
        new_cat = ServiceCategories(service_lane_id=lane_id, name=cat.name)
        db.add(new_cat)
        db.flush()
        cat_id = str(new_cat.id)
    goal = db.query(ServiceCategoryGoals).filter(ServiceCategoryGoals.category_id == cat_id,
                                                  ServiceCategoryGoals.year == year).first()
    if goal:
        goal.target_goal = cat.target_goal
    else:
        db.add(ServiceCategoryGoals(category_id=cat_id, year=year, target_goal=cat.target_goal))
    db.commit()
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="CATEGORY_CREATE",
                    resource_type="CATEGORY", resource_id=str(cat_id),
                    details=f"Category {cat.name} created/updated. Goal {cat.target_goal}.")
    return {"id": cat_id, "message": f"Category goal for {year} saved."}


def update_category(db: Session, cat_id: str, cat, year: int, current_user: dict):
    category = db.query(ServiceCategories).filter(ServiceCategories.id == cat_id).first()
    if category:
        category.service_lane_id = str(cat.service_lane_id) if cat.service_lane_id else None
        category.name = cat.name
    goal = db.query(ServiceCategoryGoals).filter(ServiceCategoryGoals.category_id == cat_id, ServiceCategoryGoals.year == year).first()
    if goal:
        goal.target_goal = cat.target_goal
    else:
        db.add(ServiceCategoryGoals(category_id=cat_id, year=year, target_goal=cat.target_goal))
    db.commit()
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="CATEGORY_UPDATE", resource_type="CATEGORY", resource_id=str(cat_id), details=f"Category {cat.name} updated for {year}.")
    return {"message": f"Category updated for year {year}"}


def delete_category(db: Session, cat_id: str, current_user: dict):
    category = db.query(ServiceCategories).filter(ServiceCategories.id == cat_id).first()
    if not category: raise HTTPException(status_code=404, detail="Category not found.")
    cat_name = category.name
    try:
        db.delete(category)
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=400, detail="Cannot delete this category because it is actively used by tests.")
    log_audit_event(user_id=str(current_user["id"]), role=current_user.get("role", "admin"), action="CATEGORY_DELETE", resource_type="CATEGORY", resource_id=str(cat_id), details=f"Category {cat_name} deleted.")
    return {"message": "Category deleted successfully"}


# --- EVENTS ---
def create_event(db: Session, e, current_user: dict):
    e_type = e.event_type.value if hasattr(e.event_type, 'value') else e.event_type
    if current_user['role'] == 'pentester':
        if e_type in ['national_holiday', 'team_day']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="Only Admins can create System-wide events.")
        e.user_id = current_user['id']
    if e_type in ['national_holiday', 'team_day']:
        e.user_id = None
        if e_type == 'team_day':
            global_loc = db.query(Locations).filter(Locations.name == 'Global').first()
            e.location_id = global_loc.id if global_loc else None
    u_id = str(e.user_id) if e.user_id else None
    loc_id = str(e.location_id) if e.location_id else None
    new_event = Events(
        user_id=u_id,
        event_type=e_type,
        location_id=loc_id,
        start_date=e.start_date,
        end_date=e.end_date
    )
    db.add(new_event)
    db.flush()
    new_event_id = str(new_event.id)
    rebalance_affected_assignments(db, e.start_date, e.end_date, u_id, loc_id)
    db.commit()
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="EVENT_CREATED",
                    resource_type="EVENTS", resource_id=new_event_id, details=f"Event {e_type} created.")
    return {"status": "ok"}


def update_event(db: Session, event_id: str, e, current_user: dict):
    event = db.query(Events).filter(Events.id == event_id).first()
    if not event: raise HTTPException(status_code=404, detail="Event not found")
    loc_id = str(e.location_id) if e.location_id else None
    e_type = e.event_type.value if hasattr(e.event_type, 'value') else e.event_type
    event.event_type = e_type
    event.location_id = loc_id
    event.start_date = e.start_date
    event.end_date = e.end_date
    current_u_id = str(event.user_id) if event.user_id else None
    rebalance_affected_assignments(db, e.start_date, e.end_date, current_u_id, loc_id)
    db.commit()
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="EVENT_UPDATED",
                    resource_type="EVENTS", resource_id=str(event_id), details=f"Event updated.")
    return {"message": "Event updated"}


def delete_event(db: Session, event_id: str, current_user: dict):
    event = db.query(Events).filter(Events.id == event_id).first()
    if not event: raise HTTPException(status_code=404, detail="Event not found")
    if current_user['role'] == 'pentester':
        if str(event.user_id) != str(current_user['id']) or event.event_type in ['national_holiday', 'team_day']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN,
                                detail="You can only delete your own personal time off.")
    db.delete(event)
    db.commit()
    log_audit_event(user_id=str(current_user["id"]), role=current_user["role"], action="EVENT_DELETE",
                    resource_type="EVENTS", resource_id=str(event_id), details=f"Event deleted.")
    return {"message": "Event deleted"}