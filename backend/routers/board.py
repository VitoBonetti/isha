from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Response, status, Query
from pydantic import UUID4
from typing import Optional
import uuid
from datetime import datetime, timedelta
from database import get_db_cursor, db_cursor_context
from routers.auth import get_current_user, require_admin, require_write_access
from schema import EventCreate, EventBase, ServiceCategoryCreate, ServiceCategoryBase
from websockets_manager import manager
from audit_logger import log_audit_event

router = APIRouter(prefix="/api/board", tags=["Board & Events"])


# --- 1. CAPACITY & SCHEDULING ENGINE ---
def get_user_provision_internal(cursor, user_id, year, week_number):
    """Calculates exact capacity accounting for holidays, start dates, and locations."""
    cursor.execute(
        'SELECT base_capacity, location_id, start_week, start_year, end_week, end_year FROM users WHERE id = %s',
        (str(user_id),))
    user_data = cursor.fetchone()
    if not user_data: return 0.0
    base_cap, user_location_id, start_week, start_year, end_week, end_year = user_data

    base_cap = float(base_cap or 0.0)

    if start_week is None: start_week = 1
    if start_year is None: start_year = 2024

    if year < start_year: return 0.0
    if year == start_year and week_number < start_week: return 0.0
    if end_year and year > end_year: return 0.0
    if end_year and year == end_year and end_week and week_number > end_week: return 0.0

    # FIX: Safely cast the location ID to prevent the "None" UUID crash
    safe_loc_id = str(user_location_id) if user_location_id is not None else None

    # Fetch relevant events (Personal PTO, Team Days, or Local/Global National Holidays)
    cursor.execute("""
        SELECT start_date, end_date
        FROM events
        WHERE (user_id = %s AND event_type != 'working_from_abroad')
           OR event_type = 'team_day'
           OR (event_type = 'national_holiday' AND (
               location_id = %s OR 
               location_id IS NULL OR 
               location_id = (SELECT id FROM locations WHERE name = 'Global' LIMIT 1)
           ))
    """, (str(user_id), safe_loc_id))
    events = cursor.fetchall()

    week_dates = []
    for day in range(1, 6):
        try:
            week_dates.append(datetime.strptime(f"{year}-W{week_number}-{day}", "%G-W%V-%u").strftime('%Y-%m-%d'))
        except ValueError:
            continue

    days_off = 0
    for start_date, end_date in events:
        event_dates = [(start_date + timedelta(days=i)).strftime('%Y-%m-%d') for i in
                       range((end_date - start_date).days + 1)]
        days_off += sum(1 for w in week_dates if w in event_dates)

    return max(0.0, base_cap - (days_off * 0.2))


def get_quarter_weeks(q: int, year: int):
    if q == 1: return range(1, 14)
    if q == 2: return range(14, 27)
    if q == 3: return range(27, 40)
    last_week = datetime(year, 12, 28).isocalendar()[1]
    return range(40, last_week + 1)


def calculate_weekly_capacity(cursor, user_id, year, week_number):
    provision = get_user_provision_internal(cursor, user_id, year, week_number)
    cursor.execute('''
        SELECT SUM(a.allocated_credits) 
        FROM assignments a
        JOIN tests t ON a.test_id = t.id
        -- FIX: Changed t.status to t.stages::text to match the database schema
        WHERE a.user_id = %s AND a.year = %s AND a.week_number = %s AND t.stages::text != 'Unable'
    ''', (str(user_id), year, week_number))

    used = cursor.fetchone()[0] or 0.0
    return max(0.0, round(provision - used, 1))


# --- AUTO-REBALANCER ---
def rebalance_user_week_assignments(cursor, user_id, year, week_number):
    provision = get_user_provision_internal(cursor, user_id, year, week_number)

    # Get current assignments for this week
    cursor.execute('''
        SELECT a.id, a.allocated_credits, t.name 
        FROM assignments a
        JOIN tests t ON a.test_id = t.id
        WHERE a.user_id = %s AND a.year = %s AND a.week_number = %s
        ORDER BY a.allocated_credits DESC
    ''', (str(user_id), year, week_number))

    assignments = cursor.fetchall()
    if not assignments: return

    total_used = sum(a[1] for a in assignments)

    # If assignments exceed the new lowered capacity, shrink them
    if total_used > provision:
        excess = total_used - provision
        for asg_id, alloc, t_name in assignments:
            if excess <= 0: break

            reduction = min(alloc, excess)
            new_alloc = round(alloc - reduction, 1)
            excess -= reduction

            if new_alloc > 0:
                cursor.execute("UPDATE assignments SET allocated_credits = %s WHERE id = %s", (new_alloc, asg_id))
                # Notify the user their hours were cut
                cursor.execute(
                    "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (str(uuid.uuid4()), str(user_id),
                     f"Your capacity on '{t_name}' (Wk {week_number}) was reduced to {new_alloc}cr due to time off.",
                     "WARNING"))
            else:
                cursor.execute("DELETE FROM assignments WHERE id = %s", (asg_id,))
                cursor.execute(
                    "INSERT INTO notifications (id, user_id, message, type, created_at) VALUES (%s, %s, %s, %s, CURRENT_TIMESTAMP)",
                    (str(uuid.uuid4()), str(user_id),
                     f"You were removed from '{t_name}' (Wk {week_number}) due to time off.", "REMOVAL"))


def rebalance_affected_assignments(cursor, start_date, end_date, user_id=None, location_id=None):
    affected_weeks = set()
    d = start_date
    while d <= end_date:
        iso = d.isocalendar()
        affected_weeks.add((iso[0], iso[1]))  # (year, week)
        d += timedelta(days=1)

    users_to_rebalance = []
    if user_id:
        users_to_rebalance = [str(user_id)]
    else:
        if location_id:
            cursor.execute("SELECT id FROM users WHERE location_id = %s", (str(location_id),))
        else:
            cursor.execute("SELECT id FROM users")
        users_to_rebalance = [str(r[0]) for r in cursor.fetchall()]

    for u in users_to_rebalance:
        for y, w in affected_weeks:
            rebalance_user_week_assignments(cursor, u, y, w)


# --- THE MAIN BOARD PAYLOAD ---
@router.get("/{year}/Q{quarter}")
def get_quarterly_board(year: int, quarter: int, response: Response,
                        current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    weeks = list(get_quarter_weeks(quarter, year))
    weeks_in_prev_year = datetime(year - 1, 12, 28).isocalendar()[1]

    # 1. Services & Categories
    cursor.execute('''
            SELECT sl.id, sl.name, sl.theme_color, sl.display_order, sl.max_concurrent_per_week, sl.is_active, sl.auto_provision_workspace 
            FROM services_lanes sl ORDER BY sl.display_order ASC
        ''')
    services = [{"id": str(r[0]), "name": r[1], "theme_color": r[2], "max_concurrent_per_week": r[4], "is_active": r[5],
                 "auto_provision_workspace": r[6]} for r in cursor.fetchall()]

    cursor.execute('''
            SELECT c.id, c.name, COALESCE(cg.target_goal, 0) as target_goal, c.service_lane_id 
            FROM service_categories c
            LEFT JOIN service_category_goals cg ON c.id = cg.category_id AND cg.year = %s
            ORDER BY c.name ASC
        ''', (year,))
    categories = [{"id": str(r[0]), "name": r[1], "target_goal": r[2], "service_lane_id": str(r[3]) if r[3] else None}
                  for r in cursor.fetchall()]

    # 2. Users (Pentesters) & Capacity Matrix
    cursor.execute('SELECT id, name, role, email, base_capacity, location_id FROM users')
    pentesters = [{"id": str(r[0]), "name": r[1], "role": r[2], "email": r[3], "capacity": r[4],
                   "location_id": str(r[5]) if r[5] else None} for r in cursor.fetchall()]

    # We pad the requested weeks to handle tests that spill over quarter/year boundaries in the UI modal
    extended_week_pairs = []

    # Add current quarter's weeks
    for w in weeks:
        extended_week_pairs.append((year, w))

    # Add 4 weeks BEFORE the quarter (handles backward spillover)
    prev_y, prev_w = year, weeks[0]
    for _ in range(4):
        prev_w -= 1
        if prev_w < 1:
            prev_y -= 1
            prev_w = datetime(prev_y, 12, 28).isocalendar()[1]
        extended_week_pairs.append((prev_y, prev_w))

    # Add 8 weeks AFTER the quarter (handles long forward spillover)
    next_y, next_w = year, weeks[-1]
    for _ in range(8):
        next_w += 1
        max_w = datetime(next_y, 12, 28).isocalendar()[1]
        if next_w > max_w:
            next_y += 1
            next_w = 1
        extended_week_pairs.append((next_y, next_w))

    # Build the matrix
    cap_matrix = {p["id"]: {} for p in pentesters}
    for p in pentesters:
        for y, w in extended_week_pairs:
            # We key it by week number so the frontend modal can find it instantly
            cap_matrix[p["id"]][w] = calculate_weekly_capacity(cursor, p["id"], y, w)

    # Map DB ENUM keys back to Frontend Strings
    enum_map = {
        "NOT_PLANNED": "Not Planned",
        "SCHEDULED": "Scheduled",
        "IN_PROGRESS": "In Progress",
        "STOPPED": "Stopped",
        "DELETED": "Deleted",
        "COMPLETED": "Completed",
        "ARCHIVED": "Archived"
    }

    # 3. Tests (Backlog) - Force stages::text to prevent serialization errors
    cursor.execute('''
            SELECT t.id, t.name, t.service_lane_id, t.category_id, 
                   t.credits_per_week, t.duration_weeks, t.stages::text,
                   (SELECT COUNT(*) FROM test_assets WHERE test_id = t.id),
                   EXISTS(SELECT 1 FROM secret_notes WHERE test_id = t.id),
                   t.drive_folder_url,
                   t.is_tentative, t.kiss24
            FROM tests t
            WHERE t.stages::text = 'NOT_PLANNED'
        ''')
    backlog = []
    for r in cursor.fetchall():
        backlog.append({
            "id": str(r[0]), "name": r[1], "service_lane_id": str(r[2]) if r[2] else None,
            "category_id": str(r[3]) if r[3] else None,
            "credits": r[4], "duration": r[5], "status": enum_map.get(str(r[6]), str(r[6])),
            "asset_count": r[7], "has_secret": r[8],
            "drive_folder_url": r[9],
            "is_tentative": r[10],
            "kiss24": str(r[11]) if r[11] else None
        })

    # 4. Tests (Scheduled) - Force stages::text to prevent serialization errors
    cursor.execute('''
        SELECT t.id, t.name, t.service_lane_id, t.category_id, 
            t.credits_per_week, t.duration_weeks, t.start_week, t.start_year, t.stages::text,
            (SELECT COUNT(*) FROM test_assets WHERE test_id = t.id),
            EXISTS(SELECT 1 FROM secret_notes WHERE test_id = t.id),
            t.drive_folder_url,
            t.is_tentative, t.kiss24
        FROM tests t
        WHERE t.stages::text IN ('SCHEDULED', 'IN_PROGRESS', 'STOPPED', 'COMPLETED') 
            AND (
                (t.start_year = %s AND (t.start_week + t.duration_weeks - 1) >= %s AND t.start_week <= %s)
                OR 
                (t.start_year = %s - 1 AND (t.start_week + t.duration_weeks - 1) - %s >= %s)
            )
    ''', (year, weeks[0], weeks[-1], year, weeks_in_prev_year, weeks[0]))

    scheduled = []
    for r in cursor.fetchall():
        scheduled.append({
            "id": str(r[0]), "name": r[1], "service_lane_id": str(r[2]) if r[2] else None,
            "category_id": str(r[3]) if r[3] else None,
            "credits": r[4], "duration": r[5], "startWeek": r[6], "startYear": r[7],
            "status": enum_map.get(str(r[8]), str(r[8])), "asset_count": r[9], "has_secret": r[10],
            "drive_folder_url": r[11],
            "is_tentative": r[12],
            "kiss24": str(r[13]) if r[13] else None
        })

    # 5. Assignments
    cursor.execute('''
        SELECT a.test_id, a.user_id, a.week_number, u.name, a.allocated_credits 
        FROM assignments a 
        JOIN users u ON a.user_id = u.id
        WHERE a.year = %s AND a.week_number = ANY(%s)
    ''', (year, weeks))
    assignments = [
        {"test_id": str(r[0]), "user_id": str(r[1]), "week_number": r[2], "user_name": r[3], "allocated_credits": r[4]}
        for r in cursor.fetchall()]

    # 6. Events
    cursor.execute('SELECT id, user_id, event_type, location_id, start_date, end_date FROM events')
    events = [{"id": str(r[0]), "user_id": str(r[1]) if r[1] else None, "type": r[2],
               "location_id": str(r[3]) if r[3] else None, "start": r[4], "end": r[5]} for r in cursor.fetchall()]

    # 7. Placeholders
    cursor.execute('''
        SELECT id, service_lane_id, year, week, credits 
        FROM service_placeholders 
        WHERE year = %s
    ''', (year,))

    ph_columns = [desc[0] for desc in cursor.description]
    placeholders = [dict(zip(ph_columns, row)) for row in cursor.fetchall()]

    return {
        "year": year, "quarter": quarter, "weeks": weeks,
        "services": services, "categories": categories,
        "pentesters": pentesters, "capacities": cap_matrix,
        "backlog": backlog, "scheduled": scheduled,
        "assignments": assignments, "events": events, "placeholders": placeholders
    }


# --- 3. UNIVERSAL CATEGORIES ---
@router.get("/categories/")
def get_categories(year: Optional[str] = None, current_user: dict = Depends(get_current_user),
                   cursor=Depends(get_db_cursor)):
    """Fetches categories, cross-joined with their yearly goals."""
    query = '''
        SELECT c.id, c.name, COALESCE(cg.target_goal, 0) as target_goal, 
               cg.year as goal_year, c.service_lane_id, s.name as service_lane_name 
        FROM service_categories c
        LEFT JOIN service_category_goals cg ON c.id = cg.category_id
        LEFT JOIN services_lanes s ON c.service_lane_id = s.id
        WHERE 1=1
    '''
    params = []

    # Apply filter if a specific year is provided
    if year and year != 'All':
        query += " AND cg.year = %s"
        params.append(int(year))

    query += " ORDER BY cg.year DESC NULLS LAST, c.name ASC"

    cursor.execute(query, tuple(params))
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/categories/", summary="[Admin Only]")
def create_category(cat: ServiceCategoryCreate, year: int = Query(...), current_user: dict = Depends(require_admin),
                    cursor=Depends(get_db_cursor)):
    lane_id = str(cat.service_lane_id) if cat.service_lane_id else None

    # 1. Ensure the Category Exists (or Create it)
    cursor.execute("SELECT id FROM service_categories WHERE name = %s LIMIT 1", (cat.name,))
    row = cursor.fetchone()

    if row:
        cat_id = row[0]
        # Update its service lane mapping just in case
        cursor.execute("UPDATE service_categories SET service_lane_id = %s WHERE id = %s", (lane_id, cat_id))
    else:
        cat_id = str(uuid.uuid4())
        cursor.execute('INSERT INTO service_categories (id, service_lane_id, name) VALUES (%s, %s, %s)',
                       (cat_id, lane_id, cat.name))

    # 2. Upsert the Goal for the explicitly requested Year
    cursor.execute('''
        INSERT INTO service_category_goals (id, category_id, year, target_goal) VALUES (%s, %s, %s, %s)
        ON CONFLICT (category_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
    ''', (str(uuid.uuid4()), cat_id, year, cat.target_goal))

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="CATEGORY_CREATE",
        resource_type="CATEGORY",
        resource_id=str(cat_id),
        details=f"Category {cat.name} created with target goal {cat.target_goal}. Service line ID: {lane_id}",
    )

    cursor.connection.commit()
    return {"id": cat_id, "message": f"Category goal for {year} saved."}


@router.put("/categories/{cat_id}", summary="[Admin Only]")
def update_category(cat_id: str, cat: ServiceCategoryBase,
                    year: int = Query(...),
                    background_tasks: BackgroundTasks = BackgroundTasks(),
                    current_user: dict = Depends(require_admin),
                    cursor=Depends(get_db_cursor)):
    # Safely convert UUID to string for psycopg2
    lane_id = str(cat.service_lane_id) if cat.service_lane_id else None

    # 1. Update the core Category details (Name & Service Lane mapping)
    cursor.execute('UPDATE service_categories SET service_lane_id=%s, name=%s WHERE id=%s',
                   (lane_id, cat.name, cat_id))

    # 2. Upsert the Target Goal for the explicitly requested Year
    cursor.execute('''
        INSERT INTO service_category_goals (id, category_id, year, target_goal) VALUES (%s, %s, %s, %s)
        ON CONFLICT (category_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
    ''', (str(uuid.uuid4()), cat_id, year, cat.target_goal))

    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="CATEGORY_UPDATE",
        resource_type="CATEGORY",
        resource_id=str(cat_id),
        details=f"Category {cat.name} updated for year {year}. Target Goal: {cat.target_goal}. Lane ID: {lane_id}",
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Category updated for year {year}"}


@router.delete("/categories/{cat_id}", summary="[Admin Only]")
def delete_category(cat_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute('SELECT name FROM service_categories WHERE id=%s', (cat_id,))
    row = cursor.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail="Category not found.")

    service_category_name = row[0]

    try:
        # Delete the category
        cursor.execute('DELETE FROM service_categories WHERE id=%s', (cat_id,))
        cursor.connection.commit()
    except Exception as e:
        # If there's a Foreign Key constraint (e.g., tests are using this category), this catches it
        cursor.connection.rollback()
        raise HTTPException(status_code=400,
                            detail="Cannot delete this category because it is actively used by tests. Remove it from tests first.")

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user.get("role", "admin"),  # Safe fallback
        action="CATEGORY_DELETE",
        resource_type="CATEGORY",
        resource_id=str(cat_id),
        details=f"Category {service_category_name} deleted. ID: {cat_id}",
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Category deleted successfully"}


# --- 4. EVENTS ---
@router.post("/events")
def create_event(e: EventCreate, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    if current_user['role'] == 'pentester':
        if e.event_type in ['national_holiday', 'team_day']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Only Admins can create System-wide events.")
        e.user_id = current_user['id']

    if e.event_type in ['national_holiday', 'team_day']:
        e.user_id = None
        if e.event_type == 'team_day':
            cursor.execute("SELECT id FROM locations WHERE name = 'Global' LIMIT 1")
            global_loc = cursor.fetchone()
            e.location_id = global_loc[0] if global_loc else None

    # Safely convert UUIDs to strings for psycopg2
    u_id = str(e.user_id) if e.user_id else None
    loc_id = str(e.location_id) if e.location_id else None

    # Safely get string value from Enum
    e_type = e.event_type.value if hasattr(e.event_type, 'value') else e.event_type

    new_event_id = str(uuid.uuid4())

    #  check if user_id is locked to NOT NULL and unlock it automatically.
    cursor.execute("""
        SELECT is_nullable FROM information_schema.columns 
        WHERE table_name = 'events' AND column_name = 'user_id'
    """)
    row = cursor.fetchone()
    if row and row[0] == 'NO':
        cursor.execute("ALTER TABLE events ALTER COLUMN user_id DROP NOT NULL;")

    cursor.execute(
        'INSERT INTO events (id, user_id, event_type, location_id, start_date, end_date) VALUES (%s, %s, %s, %s, %s, %s)',
        (new_event_id, u_id, e_type, loc_id, e.start_date, e.end_date)
    )
    rebalance_affected_assignments(cursor, e.start_date, e.end_date, u_id, loc_id)
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="EVENT_CREATED",
        resource_type="EVENTS",
        resource_id=str(new_event_id),
        details=f"Event {e_type} created. Start:{e.start_date} End:{e.end_date}"
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"status": "ok"}


@router.put("/events/{event_id}")
def update_event(event_id: str, e: EventBase, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    # FIX: Safely convert UUID to string
    loc_id = str(e.location_id) if e.location_id else None
    e_type = e.event_type.value if hasattr(e.event_type, 'value') else e.event_type

    cursor.execute(
        'UPDATE events SET event_type=%s, location_id=%s, start_date=%s, end_date=%s WHERE id=%s',
        (e_type, loc_id, e.start_date, e.end_date, event_id)
    )
    cursor.execute("SELECT user_id FROM events WHERE id = %s", (event_id,))
    u_row = cursor.fetchone()
    current_u_id = str(u_row[0]) if u_row and u_row[0] else None
    rebalance_affected_assignments(cursor, e.start_date, e.end_date, current_u_id, loc_id)
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="EVENT_UPDATED",
        resource_type="EVENTS",
        resource_id=str(event_id),
        details=f"Event {event_id} updated."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Event updated"}


@router.delete("/events/{event_id}")
def delete_event(event_id: str, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    if current_user['role'] == 'pentester':
        cursor.execute("SELECT user_id, event_type FROM events WHERE id = %s", (event_id,))
        row = cursor.fetchone()
        if not row or str(row[0]) != current_user['id'] or row[1] in ['national_holiday', 'team_day']:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="You can only delete your own personal time off.")

    cursor.execute('DELETE FROM events WHERE id=%s', (event_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="EVENT_DELETE",
        resource_type="EVENTS",
        resource_id=str(event_id),
        details=f"Event {event_id} deleted."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Event deleted"}


@router.delete("/system/wipe", summary="[Admin Only]")
def wipe_system_data(background_tasks: BackgroundTasks,
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    FACTORY RESET:
    Wipes all planning data (Tests, Assignments, Assets, Notifications, Categories, Regions, Countries).
    Preserves structural configurations (Users, Events, Locations).
    """
    try:
        cursor.execute("""
            TRUNCATE TABLE notifications CASCADE;
            TRUNCATE TABLE countries CASCADE;
            TRUNCATE TABLE regions CASCADE;
            TRUNCATE TABLE assignments CASCADE;
            TRUNCATE TABLE test_assets CASCADE;
            TRUNCATE TABLE tests CASCADE;
            TRUNCATE TABLE assets CASCADE;
            TRUNCATE TABLE raw_assets CASCADE;
            TRUNCATE TABLE services_lanes CASCADE;
            TRUNCATE TABLE service_categories CASCADE;
            TRUNCATE TABLE asset_history CASCADE;
            TRUNCATE TABLE test_history CASCADE;
        """)
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="FACTORY_RESET",
            resource_type="DATABASE",
            resource_id="N/A",
            details="Administrator successfully wiped all transactional data (Tests, Assignments, Assets)."
        )

        # Broadcast the wipe to all connected clients
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')

        return {"message": "System data wiped successfully."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to wipe system data.")


@router.delete("/system/wipe-secrets", summary="[Admin Only]")
def wipe_all_secrets(background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):

    cursor.execute("TRUNCATE TABLE secret_notes CASCADE;")

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="WIPE_SECRETS",
        resource_type="DATABASE",
        resource_id="N/A",
        details="Administrator wiped ALL encrypted secure notes."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "All secure notes wiped."}