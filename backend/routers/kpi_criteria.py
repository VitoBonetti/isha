from fastapi import APIRouter, Depends
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import require_admin, require_admin_or_read_only
from schema import AssetCriteriaBase, EvaluateCriteriaRequest
from system_services import kpi_criteria_service

router = APIRouter(prefix="/api/asset-criteria", tags=["Asset Criteria Engine"])


@router.get("/fields", summary="Get valid asset criteria fields and their relation endpoints")
def get_valid_fields(current_user: dict = Depends(require_admin_or_read_only)):
    """Returns the schema dictionary so the frontend can dynamically build the UI."""
    return kpi_criteria_service.get_valid_fields()


@router.get("/", summary="List all asset criteria configurations")
def get_all_criteria(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    return kpi_criteria_service.get_all_criteria(db)


@router.post("/", summary="Create or update asset criteria for a year")
def upsert_criteria(payload: AssetCriteriaBase, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kpi_criteria_service.upsert_criteria(db, payload, current_user)


@router.delete("/{year}", summary="Delete criteria for a year")
def delete_criteria(year: int, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kpi_criteria_service.delete_criteria(db, year)


@router.post("/evaluate/{year}", summary="Execute evaluation engine on raw_assets")
def evaluate_assets(year: int, req: EvaluateCriteriaRequest, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return kpi_criteria_service.evaluate_assets(db, year, req, current_user)


@router.get('/dashboard-data', summary='Dashboard data. only temp endpoint')
def dashboard_data(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    return kpi_criteria_service.dashboard_data(db)