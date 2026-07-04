from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, Response
from pydantic import UUID4
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
        WHERE user_id = %s
           OR event_type = 'team_day'
           OR (event_type = 'national_holiday' AND (
               location_id = %s OR 
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


def get_quarter_weeks(q: int):
    if q == 1: return range(1, 14)
    if q == 2: return range(14, 27)
    if q == 3: return range(27, 40)
    return range(40, 53)


def calculate_weekly_capacity(cursor, user_id, year, week_number):
    provision = get_user_provision_internal(cursor, user_id, year, week_number)
    cursor.execute('''
        SELECT SUM(a.allocated_credits) 
        FROM assignments a
        JOIN tests t ON a.test_id = t.id
        WHERE a.user_id = %s AND a.year = %s AND a.week_number = %s AND t.status != 'Unable'
    ''', (str(user_id), year, week_number))

    used = cursor.fetchone()[0] or 0.0
    return max(0.0, round(provision - used, 1))


# --- 2. THE MAIN BOARD PAYLOAD ---

@router.get("/{year}/Q{quarter}")
def get_quarterly_board(year: int, quarter: int, response: Response,
                        current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    weeks = list(get_quarter_weeks(quarter))

    # 1. Services & Categories
    cursor.execute(
        'SELECT id, name, theme_color, display_order FROM services_lanes WHERE is_active = TRUE ORDER BY display_order ASC')
    services = [{"id": r[0], "name": r[1], "theme_color": r[2]} for r in cursor.fetchall()]

    cursor.execute('SELECT id, name, target_goal, service_lane_id FROM service_categories ORDER BY name ASC')
    categories = [{"id": r[0], "name": r[1], "target_goal": r[2], "service_lane_id": r[3]} for r in cursor.fetchall()]

    # 2. Users (Pentesters) & Capacity Matrix
    cursor.execute('SELECT id, name, role, email, base_capacity, location_id FROM users')
    pentesters = [{"id": r[0], "name": r[1], "role": r[2], "email": r[3], "capacity": r[4], "location_id": r[5]} for r
                  in cursor.fetchall()]

    cap_matrix = {p["id"]: {w: calculate_weekly_capacity(cursor, p["id"], year, w) for w in weeks} for p in pentesters}

    # 3. Tests (Backlog & Scheduled)
    cursor.execute('''
        SELECT t.id, t.name, t.service_lane_id, t.category_id, t.credits_per_week, t.duration_weeks, 
               t.start_week, t.start_year, t.status,
               (SELECT COUNT(*) FROM test_assets WHERE test_id = t.id) as asset_count
        FROM tests t
        WHERE t.start_week IS NULL OR t.start_year = %s
    ''', (year,))

    backlog, scheduled = [], []
    for r in cursor.fetchall():
        t_obj = {
            "id": r[0], "name": r[1], "service_lane_id": r[2], "category_id": r[3],
            "credits": r[4], "duration": r[5], "startWeek": r[6], "startYear": r[7],
            "status": r[8], "asset_count": r[9]
        }
        if r[6] is None:
            backlog.append(t_obj)
        else:
            scheduled.append(t_obj)

    # 4. Assignments
    cursor.execute('''
        SELECT a.test_id, a.user_id, a.week_number, u.name, a.allocated_credits 
        FROM assignments a 
        JOIN users u ON a.user_id = u.id
        WHERE a.year = %s
    ''', (year,))
    assignments = [{"test_id": r[0], "user_id": r[1], "week_number": r[2], "user_name": r[3], "allocated_credits": r[4]}
                   for r in cursor.fetchall()]

    # 5. Events
    cursor.execute('SELECT id, user_id, event_type, location_id, start_date, end_date FROM events')
    events = [{"id": r[0], "user_id": r[1], "type": r[2], "location_id": r[3], "start": r[4], "end": r[5]} for r in
              cursor.fetchall()]

    return {
        "year": year, "quarter": quarter, "weeks": weeks,
        "services": services, "categories": categories,
        "pentesters": pentesters, "capacities": cap_matrix,
        "backlog": backlog, "scheduled": scheduled,
        "assignments": assignments, "events": events
    }


# --- 3. UNIVERSAL CATEGORIES ---
@router.get("/categories/")
def get_categories(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """Fetches all service categories for the settings page."""
    cursor.execute('''
        SELECT c.id, c.name, c.target_goal, c.service_lane_id, s.name as service_lane_name 
        FROM service_categories c
        LEFT JOIN services_lanes s ON c.service_lane_id = s.id
        ORDER BY c.name ASC
    ''')
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


@router.post("/categories/")
def create_category(cat: ServiceCategoryCreate, current_user: dict = Depends(require_admin),
                    cursor=Depends(get_db_cursor)):
    # Safely convert UUID to string for psycopg2
    lane_id = str(cat.service_lane_id) if cat.service_lane_id else None

    new_category_id= str(uuid.uuid4())

    cursor.execute(
        'INSERT INTO service_categories (id, service_lane_id, name, target_goal) VALUES (%s, %s, %s, %s) RETURNING id',
        (new_category_id, lane_id, cat.name, cat.target_goal)
    )

    log_audit_event(
        user_id=str(current_user["id"]),
        username=current_user["name"],
        action="CATEGORY_CREATE",
        resource_type="CATEGORY",
        details=f"Category {cat.name} created with target goal {cat.target_goal}. Service line ID: {lane_id}",
    )

    new_id = cursor.fetchone()[0]
    cursor.connection.commit()
    return {"id": new_id}


@router.put("/categories/{cat_id}")
def update_category(cat_id: str, cat: ServiceCategoryBase, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute(
        'UPDATE service_categories SET service_lane_id=%s, name=%s, target_goal=%s WHERE id=%s',
        (cat.service_lane_id, cat.name, cat.target_goal, cat_id)
    )
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        username=current_user["name"],
        action="CATEGORY_UPDATE",
        resource_type="CATEGORY",
        details=f"Category {cat.name} updated. ID: {cat.service_lane_id}",
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Category updated"}


@router.delete("/categories/{cat_id}")
def delete_category(cat_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    service_category_name = cursor.execute('SELECT name FROM service_categories WHERE id=%s', (cat_id,)).fetchone()[0]
    cursor.execute('DELETE FROM service_categories WHERE id=%s', (cat_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        username=current_user["name"],
        action="CATEGORY_DELETE",
        resource_type="CATEGORY",
        details=f"Category {service_category_name} deleted. ID: {cat_id}",
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Category deleted"}


# --- 4. EVENTS ---

@router.post("/events")
def create_event(e: EventCreate, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    if current_user['role'] == 'pentester':
        if e.event_type in ['national_holiday', 'team_day']:
            raise HTTPException(status_code=403, detail="Only Admins can create System-wide events.")
        e.user_id = current_user['id']

    if e.event_type in ['national_holiday', 'team_day']:
        e.user_id = None
        if e.event_type == 'team_day':
            cursor.execute("SELECT id FROM locations WHERE name = 'Global' LIMIT 1")
            e.location_id = cursor.fetchone()[0]

    # FIX: Safely convert UUIDs to strings for psycopg2
    u_id = str(e.user_id) if e.user_id else None
    loc_id = str(e.location_id) if e.location_id else None

    # Safely get string value from Enum
    e_type = e.event_type.value if hasattr(e.event_type, 'value') else e.event_type

    new_event_id = str(uuid.uuid4())

    cursor.execute(
        'INSERT INTO events (id, user_id, event_type, location_id, start_date, end_date) VALUES (%s, %s, %s, %s, %s, %s)',
        (new_event_id, u_id, e_type, loc_id, e.start_date, e.end_date)
    )
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        username=current_user["name"],
        action="EVENT_CREATED",
        resource_type="EVENTS",
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
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        username=current_user["name"],
        action="EVENT_UPDATED",
        resource_type="EVENTS",
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
            raise HTTPException(status_code=403, detail="You can only delete your own personal time off.")

    cursor.execute('DELETE FROM events WHERE id=%s', (event_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        username=current_user["name"],
        action="EVENT_DELETE",
        resource_type="EVENTS",
        details=f"Event {event_id} deleted."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Event deleted"}


@router.delete("/system/wipe")
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
            TRUNCATE TABLE service_lanes CASCADE;
            TRUNCATE TABLE service_categories CASCADE;
        """)
        cursor.connection.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            username=current_user["name"],
            action="FACTORY_RESET",
            resource_type="DATABASE",
            details="Administrator successfully wiped all transactional data (Tests, Assignments, Assets)."
        )

        # Broadcast the wipe to all connected clients
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
        background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')

        return {"message": "System data wiped successfully."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=500, detail="Failed to wipe system data.")