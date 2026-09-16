from fastapi import APIRouter, Depends, BackgroundTasks
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import require_admin, get_current_user, require_admin_or_read_only
from schema import ContactSyncPayload
from websockets_manager import manager
from system_services import contact_service

router = APIRouter(prefix="/api/contacts", tags=["Contacts"])


@router.get("/", summary="Get All Global Contacts")
def get_all_contacts(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Endpoint to Get All Global Contacts
    """
    return contact_service.get_all_contacts(db)


@router.post("/sync", summary="[Admin Only] Create/Edit Contact & Mappings")
def sync_full_contact(payload: ContactSyncPayload, background_tasks: BackgroundTasks = BackgroundTasks(), 
                      current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Sync Full Contacts, Create/Edit Contact & Mappings
    """
    res = contact_service.sync_full_contact(db, payload, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.delete("/global/{contact_id}", summary="[Admin Only] Hard Delete Global Contact")
def delete_global_contact(contact_id: str, background_tasks: BackgroundTasks = BackgroundTasks(), 
                          current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Admin Only Endpoint to Delete Global Contact
    """
    res = contact_service.delete_global_contact(db, contact_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_ASSETS"}')
    return res


@router.get("/raw-asset/{raw_asset_id}", summary="Get Asset Contacts")
def get_asset_contacts(raw_asset_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to Get Asset Contacts
    """
    return contact_service.get_asset_contacts(db, raw_asset_id)


@router.get("/country/{country_id}", summary="Get Country Contacts")
def get_country_contacts(country_id: str, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Endpoint to Get Country Contacts
    """
    return contact_service.get_country_contacts(db, country_id)