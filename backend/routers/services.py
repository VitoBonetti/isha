from fastapi import APIRouter, Depends, BackgroundTasks
from database import get_db_cursor
from routers.auth import require_admin
from models import ServiceLaneBase
from websockets_manager import manager

router = APIRouter(prefix="/api/services", tags=["Services"])


@router.get("/")
def get_services(cursor=Depends(get_db_cursor)):
    cursor.execute('''
        SELECT id, name, max_concurrent_per_week, theme_color, 
               default_credits, default_duration_weeks, display_order 
        FROM service_lanes 
        WHERE is_active = TRUE 
        ORDER BY display_order ASC, name ASC
    ''')

    columns = [desc[0] for desc in cursor.description]
    services = [dict(zip(columns, row)) for row in cursor.fetchall()]

    # Ensure numerical types are cast correctly for the JSON response
    for s in services:
        s['default_credits'] = float(s['default_credits'] or 2.0)
        s['default_duration_weeks'] = int(s['default_duration_weeks'] or 1)

    return services


@router.post("/")
def create_service(s: ServiceLaneBase, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute(
        '''INSERT INTO service_lanes 
           (name, max_concurrent_per_week, theme_color, default_credits, default_duration_weeks, display_order) 
           VALUES (%s, %s, %s, %s, %s, %s) RETURNING id''',
        (s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits, s.default_duration_weeks, s.display_order)
    )
    new_id = cursor.fetchone()[0]
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane created", "id": new_id}


@router.put("/{service_id}")
def update_service(service_id: str, s: ServiceLaneBase, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute(
        '''UPDATE service_lanes 
           SET name=%s, max_concurrent_per_week=%s, theme_color=%s, 
               default_credits=%s, default_duration_weeks=%s, display_order=%s 
           WHERE id=%s''',
        (s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits, s.default_duration_weeks, s.display_order,
         service_id)
    )
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane updated"}


@router.delete("/{service_id}")
def delete_service(service_id: str, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    # Soft delete to preserve historical integrity on the board
    cursor.execute("UPDATE service_lanes SET is_active = FALSE WHERE id = %s", (service_id,))
    cursor.connection.commit()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return {"message": "Service lane deactivated"}