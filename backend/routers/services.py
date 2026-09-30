from fastapi import APIRouter, Depends, BackgroundTasks, Query
from datetime import datetime
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_maintainer_or_admin, require_admin_or_read_only
from schema import ServiceLaneBase, PlaceholderResponse, PlaceholderCreate, ServiceLaneTemplatesUpdate
from websockets_manager import manager
from system_services import service_lane_service
from utils.memory_cache import invalidate_board_cache

router = APIRouter(prefix="/api/services", tags=["Services"])


@router.get(
    "/",
    summary="Get All Service Lanes"
)
def get_services(year: int = Query(default_factory=lambda: datetime.now().year),
                 current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve all operational Service Lanes.

    Fetches the configured list of active testing teams and service lanes (e.g., Red Team, AppSec, Cloud).
    Requires a specific year parameter to correctly calculate live capacity constraints.
    """
    return service_lane_service.get_services(db, year, current_user)


@router.post(
    "/",
    summary="[Admin Only] Create Service Lane"
)
def create_service(s: ServiceLaneBase, year: int = Query(default_factory=lambda: datetime.now().year),
                   background_tasks: BackgroundTasks = BackgroundTasks(),
                   current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Define a new Service Lane.

    Creates a new organizational division for processing tests, automatically assigning
    default goals and workspace provisioning rules. Triggers a global UI refresh upon creation.
    """
    res = service_lane_service.create_service(db, s, year, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put(
    "/{service_id}",
    summary="[Admin Only] Update Service Lane"
)
def update_service(service_id: str, s: ServiceLaneBase, year: int = Query(default_factory=lambda: datetime.now().year),
                   background_tasks: BackgroundTasks = BackgroundTasks(),
                   current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Modify an existing Service Lane's operational settings.

    Updates properties like lane naming, active status, color coding, and automatic workspace
    provisioning toggles.
    """
    res = service_lane_service.update_service(db, service_id, s, year, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete(
    "/{service_id}",
    summary="[Admin Only] Delete Service Lane"
)
def delete_service(service_id: str, background_tasks: BackgroundTasks,
                   current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Permanently delete a Service Lane.

    Removes the lane and drops all associated placeholder tasks. Will fail if there are
    actual operational tests currently assigned to it.
    """
    res = service_lane_service.delete_service(db, service_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.get(
    "/{service_id}/goals",
    summary="Get Service Lane Goals"
)
def get_service_goals(service_id: str, current_user: dict = Depends(require_admin_or_read_only),
                      db: Session = Depends(get_db)):
    """
    Retrieve yearly targets for a specific Service Lane.

    Fetches the complete historical and future ledger of configured capacity targets
    (credits) expected from this team per year.
    """
    return service_lane_service.get_service_goals(db, service_id)


@router.post(
    "/{service_id}/goals",
    summary="[Admin Only] Set Service Goal"
)
def set_service_goal(service_id: str, year: int = Query(...), target_goal: int = Query(...),
                     background_tasks: BackgroundTasks = BackgroundTasks(),
                     current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Define the total expected credit output for a service lane in a given year.

    Upserts the target capacity limit into the database to calculate real-time team utilization on the dashboard.
    """
    res = service_lane_service.set_service_goal(db, service_id, year, target_goal, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


# -- Placeholders endpoints ---
@router.post(
    "/placeholders",
    response_model=PlaceholderResponse,
    summary="[Admin Only] Create Placeholder"
)
def create_placeholder(p: PlaceholderCreate, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Reserve visual capacity on the Kanban board.

    Creates a temporary, unlinked placeholder block on the calendar to reserve week/credits
    for an incoming task before it officially gets converted into a test.
    """
    res = service_lane_service.create_placeholder(db, p, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete(
    "/placeholders/{placeholder_id}",
    summary="[Admin Only] Delete Placeholder"
)
def delete_placeholder(placeholder_id: str, background_tasks: BackgroundTasks,
                       current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Remove a reserved capacity block from the board.
    """
    res = service_lane_service.delete_placeholder(db, placeholder_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.patch(
    "/{service_lane_id}/templates",
    summary="[Admin/Maintainer] Update Automated Templates"
)
def update_service_lane_templates(
        service_lane_id: str,
        payload: ServiceLaneTemplatesUpdate,
        current_user: dict = Depends(require_maintainer_or_admin),
        db: Session = Depends(get_db)
):
    """
    Modify system-generated communication templates.

    Update the HTML structures used for the automated Intro and Final output emails for a specific service lane.
    """
    return service_lane_service.update_service_lane_templates(db, service_lane_id, payload, current_user)