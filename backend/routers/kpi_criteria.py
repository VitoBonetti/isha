from fastapi import APIRouter, Depends
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import require_admin, require_admin_or_read_only
from schema import AssetCriteriaBase, EvaluateCriteriaRequest
from system_services import kpi_criteria_service

router = APIRouter(prefix="/api/asset-criteria", tags=["Asset Criteria Engine"])


@router.get("/fields", summary="Get Configurable Criteria Fields")
def get_valid_fields(current_user: dict = Depends(require_admin_or_read_only)):
    """
    Retrieve the dynamic schema dictionary of configurable fields.

    Returns the strict mapping of logical operators and fields available for building
    dynamic KPI criteria rules on the frontend.
    """
    return kpi_criteria_service.get_valid_fields()


@router.get("/", summary="List All Criteria Configurations")
def get_all_criteria(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Fetch every configured KPI criteria rule set currently active across all operational years.
    """
    return kpi_criteria_service.get_all_criteria(db)


@router.post("/", summary="[Admin Only] Upsert Asset Criteria")
def upsert_criteria(payload: AssetCriteriaBase, current_user: dict = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """
    Create or overwrite the complex JSON rule tree that dictates whether an asset
    should be automatically flagged as a KPI or Critical entity for a specific year.
    """
    return kpi_criteria_service.upsert_criteria(db, payload, current_user)


@router.delete("/{year}", summary="[Admin Only] Delete Yearly Criteria")
def delete_criteria(year: int, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Completely remove the configured asset KPI criteria logic for the specified year.
    """
    return kpi_criteria_service.delete_criteria(db, year)


@router.post("/evaluate/{year}", summary="[Admin Only] Execute Evaluation Engine")
def evaluate_assets(year: int, req: EvaluateCriteriaRequest, current_user: dict = Depends(require_admin),
                    db: Session = Depends(get_db)):
    """
    Trigger the criteria engine to evaluate raw assets.

    Reads the configured JSON rule tree for the specified year and executes a mass update against
    the raw_assets table, automatically flagging qualifying assets as 'is_kpi' or 'is_critical'.
    """
    return kpi_criteria_service.evaluate_assets(db, year, req, current_user)


@router.get('/dashboard-data', summary="Get Temporary Dashboard Data")
def dashboard_data(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Retrieve lightweight data aggregations for temporary dashboard views.
    """
    return kpi_criteria_service.dashboard_data(db)