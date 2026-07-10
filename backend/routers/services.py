from fastapi import APIRouter, Depends, BackgroundTasks
from database import get_db_cursor
from routers.auth import require_admin, get_current_user
from schema import ServiceLaneBase
from websockets_manager import manager
import uuid

router = APIRouter(prefix="/api/services", tags=["Services"])

@router.get("/")
def get_services(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    cursor.execute('''
        SELECT id, name, max_concurrent_per_week, theme_color, 
               default_credits, default_duration_weeks, display_order, is_active
        FROM services_lanes 
        WHERE is_active IS TRUE OR is_active IS NULL
        ORDER BY display_order ASC, name ASC
    ''')

    columns = [desc[0] for desc in cursor.description]
    services = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for s in services:
        s['default_credits'] = float(s['default_credits'] or 2.0)
        s['default_duration_weeks'] = int(s['default_duration_weeks'] or 1)

    return services


@router.post("/", summary="[Admin Only]")
def create_service(s: ServiceLaneBase, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    new_service_id = str(uuid.uuid4())
    cursor.execute(
        '''INSERT INTO services_lanes 
           (id, name, max_concurrent_per_week, theme_color, default_credits, default_duration_weeks, display_order, is_active) 
           VALUES (%s, %s, %s, %s, %s, %s, %s, TRUE)
           ON CONFLICT (name) DO UPDATE 
           SET is_active = TRUE,
               max_concurrent_per_week = EXCLUDED.max_concurrent_per_week,
               theme_color = EXCLUDED.theme_color,
               default_credits = EXCLUDED.default_credits,
               default_duration_weeks = EXCLUDED.default_duration_weeks,
               display_order = EXCLUDED.display_order
           RETURNING id''',
        (new_service_id, s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits, s.default_duration_weeks,
         s.display_order)
    )
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane created or restored", "id": new_service_id}


@router.put("/{service_id}", summary="[Admin Only]")
def update_service(service_id: str, s: ServiceLaneBase, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute(
        '''UPDATE services_lanes 
           SET name=%s, max_concurrent_per_week=%s, theme_color=%s, 
               default_credits=%s, default_duration_weeks=%s, display_order=%s 
           WHERE id=%s''',
        (s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits, s.default_duration_weeks, s.display_order,
         service_id)
    )
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane updated"}


@router.delete("/{service_id}", summary="[Admin Only]")
def delete_service(service_id: str, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("UPDATE services_lanes SET is_active = FALSE WHERE id = %s", (service_id,))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane deactivated"}