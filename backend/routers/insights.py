from fastapi import APIRouter, Depends
from typing import Optional
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import require_admin_or_read_only
from system_services import insight_service

router = APIRouter(prefix="/api/insights", tags=["Insights"])


@router.get("/available-years", summary="[Admin Only]")
def get_available_years(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Get Available Years
    """
    return insight_service.get_available_years(db)


@router.get("/", summary="[Admin Only]")
def get_yearly_insights(year: Optional[int] = None, current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Get Yearly Insights
    """
    return insight_service.get_yearly_insights(db, year)