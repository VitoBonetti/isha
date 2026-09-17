from fastapi import APIRouter, Depends, BackgroundTasks, Response, Query
from typing import Optional
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_write_access
from schema import EventCreate, EventBase, ServiceCategoryCreate, ServiceCategoryBase
from websockets_manager import manager
from system_services import board_service
from utils.memory_cache import get_cached_json, set_cached_json, invalidate_board_cache

router = APIRouter(prefix="/api/board", tags=["Board & Events"])


# --- THE MAIN BOARD PAYLOAD (CACHED) ---
@router.get("/{year}/Q{quarter}")
def get_quarterly_board(year: int, quarter: int, response: Response,
                        current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    # Prevent browser-level caching so the client always hits FastAPI or Redis
    response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"

    role = current_user.get("role", "read_only")
    lane_id = current_user.get("service_lane_id", "global")
    cache_key = f"board:{year}:Q{quarter}:{role}:{lane_id}"

    # 1. Check Redis Cache
    if cached_payload := get_cached_json(cache_key):
        return cached_payload

    # 2. Cache Miss: Execute SQL logic
    board_payload = board_service.get_quarterly_board(db, year, quarter, current_user)

    # 3. Store in Redis (1 Hour TTL)
    set_cached_json(cache_key, board_payload, ttl=3600)

    return board_payload


# --- UNIVERSAL CATEGORIES ---
@router.get("/categories/")
def get_categories(year: Optional[str] = None, current_user: dict = Depends(get_current_user),
                   db: Session = Depends(get_db)):
    return board_service.get_categories(db, year)


@router.post("/categories/", summary="[Admin Only]")
def create_category(cat: ServiceCategoryCreate, year: int = Query(...), current_user: dict = Depends(require_admin),
                    db: Session = Depends(get_db)):
    res = board_service.create_category(db, cat, year, current_user)
    invalidate_board_cache()
    return res


@router.put("/categories/{cat_id}", summary="[Admin Only]")
def update_category(cat_id: str, cat: ServiceCategoryBase, year: int = Query(...),
                    background_tasks: BackgroundTasks = BackgroundTasks(),
                    current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    res = board_service.update_category(db, cat_id, cat, year, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/categories/{cat_id}", summary="[Admin Only]")
def delete_category(cat_id: str, background_tasks: BackgroundTasks,
                    current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    res = board_service.delete_category(db, cat_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


# --- EVENTS ---
@router.post("/events")
def create_event(e: EventCreate, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), db: Session = Depends(get_db)):
    res = board_service.create_event(db, e, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/events/{event_id}")
def update_event(event_id: str, e: EventBase, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), db: Session = Depends(get_db)):
    res = board_service.update_event(db, event_id, e, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/events/{event_id}")
def delete_event(event_id: str, background_tasks: BackgroundTasks,
                 current_user: dict = Depends(require_write_access), db=Depends(get_db)):
    res = board_service.delete_event(db, event_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res