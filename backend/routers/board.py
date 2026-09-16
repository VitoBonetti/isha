from fastapi import APIRouter, Depends, BackgroundTasks, Response, Query
from typing import Optional
from database import get_db_cursor
from routers.auth import get_current_user, require_admin, require_write_access
from schema import EventCreate, EventBase, ServiceCategoryCreate, ServiceCategoryBase
from websockets_manager import manager
from system_services import board_service

router = APIRouter(prefix="/api/board", tags=["Board & Events"])


# --- THE MAIN BOARD PAYLOAD ---
@router.get("/{year}/Q{quarter}")
def get_quarterly_board(year: int, quarter: int, response: Response,
                        current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    # Prevent caching of dynamic capacity data
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    return board_service.get_quarterly_board(cursor, year, quarter, current_user)


# --- UNIVERSAL CATEGORIES ---
@router.get("/categories/")
def get_categories(year: Optional[str] = None, current_user: dict = Depends(get_current_user),
                   cursor=Depends(get_db_cursor)):
    return board_service.get_categories(cursor, year)


@router.post("/categories/", summary="[Admin Only]")
def create_category(cat: ServiceCategoryCreate, year: int = Query(...), current_user: dict = Depends(require_admin),
                    cursor=Depends(get_db_cursor)):
    return board_service.create_category(cursor, cat, year, current_user)


@router.put("/categories/{cat_id}", summary="[Admin Only]")
def update_category(cat_id: str, cat: ServiceCategoryBase, year: int = Query(...),
                    background_tasks: BackgroundTasks = BackgroundTasks(),
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = board_service.update_category(cursor, cat_id, cat, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/categories/{cat_id}", summary="[Admin Only]")
def delete_category(cat_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    res = board_service.delete_category(cursor, cat_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


# --- EVENTS ---
@router.post("/events")
def create_event(e: EventCreate, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    res = board_service.create_event(cursor, e, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/events/{event_id}")
def update_event(event_id: str, e: EventBase, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    res = board_service.update_event(cursor, event_id, e, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/events/{event_id}")
def delete_event(event_id: str, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), cursor=Depends(get_db_cursor)):
    res = board_service.delete_event(cursor, event_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res