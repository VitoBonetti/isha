from fastapi import APIRouter, Depends, BackgroundTasks, Query, HTTPException
from database import get_db_cursor
from routers.auth import (
    get_current_user,
    require_admin,
    require_write_access,
    require_maintainer_or_admin,
    verify_lane_access
)
from schema import ServiceLaneBase, PlaceholderResponse, PlaceholderCreate, ServiceLaneTemplatesUpdate
from websockets_manager import manager
import uuid
from datetime import datetime
from audit_logger import log_audit_event

router = APIRouter(prefix="/api/services", tags=["Services"])


@router.get("/")
def get_services(year: int = Query(default_factory=lambda: datetime.now().year),
                 current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    """
    Endpoint to get all services
    """
    where_clauses = []

    # Note: `year` is our first parameter because of the LEFT JOIN condition
    params = [year]

    # 1. Restrict maintainers to their assigned service lane
    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        if lane_id:
            where_clauses.append("sl.id = %s")
            params.append(str(lane_id))
        else:
            # Safely return nothing if the Maintainer hasn't been assigned a lane yet
            where_clauses.append("sl.id = '00000000-0000-0000-0000-000000000000'")

    # 2. Build the dynamic WHERE string
    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    # 3. Inject it into the query using an f-string
    cursor.execute(f'''
        SELECT sl.id, sl.name, sl.max_concurrent_per_week, sl.theme_color, 
                sl.default_credits, sl.default_duration_weeks, sl.display_order, sl.is_active,
                sl.auto_provision_workspace, 
                sl.intro_email_template, sl.final_email_template, sl.requires_mitre, 
                COALESCE(slg.target_goal, 0) as target_goal
        FROM services_lanes sl
        LEFT JOIN service_lane_goals slg ON sl.id = slg.service_lane_id AND slg.year = %s
        {where_str}
        ORDER BY sl.display_order ASC, sl.name ASC
    ''', tuple(params))

    columns = [desc[0] for desc in cursor.description]
    services = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for s in services:
        s['default_credits'] = float(s['default_credits'] or 2.0)
        s['default_duration_weeks'] = int(s['default_duration_weeks'] or 1)
        s['target_goal'] = int(s['target_goal'] or 0)

    return services


@router.post("/", summary="[Admin Only]")
def create_service(s: ServiceLaneBase, year: int = Query(default_factory=lambda: datetime.now().year), background_tasks: BackgroundTasks = BackgroundTasks(),
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to create a new service
    """
    new_service_id = str(uuid.uuid4())
    cursor.execute(
        '''INSERT INTO services_lanes 
            (id, name, max_concurrent_per_week, theme_color, default_credits, default_duration_weeks, display_order, is_active, auto_provision_workspace, requires_mitre)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (name) DO UPDATE 
            SET is_active = EXCLUDED.is_active,
               max_concurrent_per_week = EXCLUDED.max_concurrent_per_week,
               theme_color = EXCLUDED.theme_color,
               default_credits = EXCLUDED.default_credits,
               default_duration_weeks = EXCLUDED.default_duration_weeks,
               display_order = EXCLUDED.display_order,
               auto_provision_workspace = EXCLUDED.auto_provision_workspace,
               requires_mitre = EXCLUDED.requires_mitre
           RETURNING id''',
        (new_service_id, s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits,
         s.default_duration_weeks, s.display_order, s.is_active, s.auto_provision_workspace, s.requires_mitre)
    )
    returned_id = cursor.fetchone()[0]

    cursor.execute('''
            INSERT INTO service_lane_goals (id, service_lane_id, year, target_goal)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (service_lane_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
        ''', (str(uuid.uuid4()), returned_id, year, s.target_goal))

    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SERVICES_LANES_CREATED",
        resource_type="SERVICES_LANES",
        resource_id=str(new_service_id),
        details=f"Service Lane {s.name} with ID: {new_service_id} was created."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane created or restored", "id": new_service_id}


@router.put("/{service_id}", summary="[Admin Only]")
def update_service(service_id: str, s: ServiceLaneBase, year: int = Query(default_factory=lambda: datetime.now().year),
                   background_tasks: BackgroundTasks = BackgroundTasks(),
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to update a service
    """
    cursor.execute(
        '''UPDATE services_lanes 
            SET name=%s, max_concurrent_per_week=%s, theme_color=%s,
                default_credits=%s, default_duration_weeks=%s, display_order=%s, is_active=%s,
                auto_provision_workspace=%s, requires_mitre=%s
            WHERE id=%s''',
        (s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits,
         s.default_duration_weeks, s.display_order, s.is_active, s.auto_provision_workspace, s.requires_mitre, service_id)
    )

    # UPSERT THE GOAL FOR THE YEAR
    cursor.execute('''
        INSERT INTO service_lane_goals (id, service_lane_id, year, target_goal)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (service_lane_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
    ''', (str(uuid.uuid4()), service_id, year, s.target_goal))

    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SERVICES_LANES_UPDATED",
        resource_type="SERVICES_LANES",
        resource_id=str(service_id),
        details=f"Service Lane  with ID: {service_id} was updated."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane updated"}


@router.delete("/{service_id}", summary="[Admin Only]")
def delete_service(service_id: str, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to delete a service
    """

    cursor.execute('DELETE FROM services_lanes WHERE id = %s', (service_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SERVICES_LANES_DELETED",
        resource_type="SERVICES_LANES",
        resource_id=str(service_id),
        details=f"Service Lane  with ID: {service_id} was deleted."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane deleted"}


@router.get("/{service_id}/goals")
def get_service_goals(service_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Fetches the complete ledger of yearly goals for a single Service Lane.
    """
    cursor.execute("""
        SELECT year, target_goal 
        FROM service_lane_goals 
        WHERE service_lane_id = %s 
        ORDER BY year DESC
    """, (service_id,))
    return [{"year": r[0], "target_goal": r[1]} for r in cursor.fetchall()]


@router.post("/{service_id}/goals", summary="[Admin Only]")
def set_service_goal(service_id: str, year: int = Query(...), target_goal: int = Query(...),
                     background_tasks: BackgroundTasks = BackgroundTasks(),
                     current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only endpoint to Upserts a specific year's goal into the ledger.
    """
    cursor.execute('''
        INSERT INTO service_lane_goals (id, service_lane_id, year, target_goal) 
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (service_lane_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
    ''', (str(uuid.uuid4()), service_id, year, target_goal))

    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": f"Goal for {year} saved successfully."}


# -- Placeholders endopints ---
@router.post("/placeholders", response_model=PlaceholderResponse, summary="[Admin Only]")
def create_placeholder(p: PlaceholderCreate, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to create a new placeholder
    """
    new_placeholder_id = str(uuid.uuid4())
    default_credits = 2

    cursor.execute(
        '''INSERT INTO service_placeholders 
            (id, service_lane_id, year, week, credits)
            VALUES (%s, %s, %s, %s, %s)
           RETURNING id, service_lane_id, year, week, credits''',
        (new_placeholder_id, p.service_lane_id, p.year, p.week, default_credits)
    )
    row = cursor.fetchone()
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="PLACEHOLDER_CREATED",
        resource_type="SERVICE_PLACEHOLDERS",
        resource_id=new_placeholder_id,
        details=f"Placeholder created for service {p.service_lane_id} in week {p.week} of {p.year}."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')

    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


@router.delete("/placeholders/{placeholder_id}", summary="[Admin Only]")
def delete_placeholder(placeholder_id: str, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    """
    Admin Only Endpoint to Delete a placeholder
    """

    cursor.execute('DELETE FROM service_placeholders WHERE id = %s', (placeholder_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="PLACEHOLDER_DELETED",
        resource_type="SERVICE_PLACEHOLDERS",
        resource_id=placeholder_id,
        details=f"Placeholder {placeholder_id} was deleted."
    )

    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Placeholder deleted"}


@router.patch("/{service_lane_id}/templates", summary="[Admin/Maintainer]")
def update_service_lane_templates(
        service_lane_id: str,
        payload: ServiceLaneTemplatesUpdate,
        current_user: dict = Depends(require_maintainer_or_admin),
        cursor=Depends(get_db_cursor)
):
    """
    Admin/Maintainer Endpoint to update service lane templates
    """
    verify_lane_access(current_user, str(service_lane_id))

    # Update the templates in the database
    cursor.execute("""
        UPDATE services_lanes
        SET intro_email_template = COALESCE(%s, intro_email_template),
            final_email_template = COALESCE(%s, final_email_template)
        WHERE id = %s
        RETURNING id;
    """, (payload.intro_email_template, payload.final_email_template, service_lane_id))

    updated_id = cursor.fetchone()
    if not updated_id:
        raise HTTPException(status_code=404, detail="Service Lane not found")

    cursor.connection.commit()
    return {"status": "Success", "message": "Templates updated successfully"}