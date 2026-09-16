from fastapi import APIRouter, Depends, BackgroundTasks, Query
from datetime import datetime
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_maintainer_or_admin, require_admin_or_read_only
from schema import ServiceLaneBase, PlaceholderResponse, PlaceholderCreate, ServiceLaneTemplatesUpdate
from websockets_manager import manager
from system_services import service_lane_service

router = APIRouter(prefix="/api/services", tags=["Services"])


@router.get("/")
def get_services(year: int = Query(default_factory=lambda: datetime.now().year),
                 current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to get all services
    """
    return service_lane_service.get_services(db, year, current_user)


@router.post("/", summary="[Admin Only]")
def create_service(s: ServiceLaneBase, year: int = Query(default_factory=lambda: datetime.now().year), background_tasks: BackgroundTasks = BackgroundTasks(),
                   current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to create a new service
    """
    res = service_lane_service.create_service(db, s, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/{service_id}", summary="[Admin Only]")
def update_service(service_id: str, s: ServiceLaneBase, year: int = Query(default_factory=lambda: datetime.now().year),
                   background_tasks: BackgroundTasks = BackgroundTasks(),
                   current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to update a service
    """
    res = service_lane_service.update_service(db, service_id, s, year, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/{service_id}", summary="[Admin Only]")
def delete_service(service_id: str, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to delete a service
    """
    res = service_lane_service.delete_service(db, service_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.get("/{service_id}/goals")
def get_service_goals(service_id: str, current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Fetches the complete ledger of yearly goals for a single Service Lane.
    """
    return service_lane_service.get_service_goals(db, service_id)


@router.post("/{service_id}/goals", summary="[Admin Only]")
def set_service_goal(service_id: str, year: int = Query(...), target_goal: int = Query(...),
                     background_tasks: BackgroundTasks = BackgroundTasks(),
                     current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only endpoint to Upserts a specific year's goal into the ledger.
    """
    res = service_lane_service.set_service_goal(db, service_id, year, target_goal, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


# -- Placeholders endpoints ---
@router.post("/placeholders", response_model=PlaceholderResponse, summary="[Admin Only]")
def create_placeholder(p: PlaceholderCreate, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to create a new placeholder
    """
    res = service_lane_service.create_placeholder(db, p, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/placeholders/{placeholder_id}", summary="[Admin Only]")
def delete_placeholder(placeholder_id: str, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Delete a placeholder
    """
    res = service_lane_service.delete_placeholder(db, placeholder_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.patch("/{service_lane_id}/templates", summary="[Admin/Maintainer]")
def update_service_lane_templates(
        service_lane_id: str,
        payload: ServiceLaneTemplatesUpdate,
        current_user: dict = Depends(require_maintainer_or_admin),
        db: Session = Depends(get_db)
):
    """
    Admin/Maintainer Endpoint to update service lane templates
    """
    return service_lane_service.update_service_lane_templates(db, service_lane_id, payload, current_user)