from fastapi import APIRouter, Depends, BackgroundTasks
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_admin_or_read_only
from schema import UserCreate, UserBase, Kiss24KeyUpdate, PublicKeyUpdate
from websockets_manager import manager
from system_services import user_service

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get("/system/status")
def check_system_status(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    return user_service.check_system_status(db)


@router.get("/system/time", summary="Get Server Time")
def get_system_time(current_user: dict = Depends(get_current_user)):
    return user_service.get_system_time()


@router.get("/", summary="[Admin Only]")
def get_all_users(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    return user_service.get_all_users(db)


@router.post("/", summary="[Admin Only]")
def create_user(u: UserCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    res = user_service.create_user(db, u, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete("/{user_id}", summary="[Admin Only]")
def delete_user(user_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    res = user_service.delete_user(db, user_id, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put("/{user_id}", summary="[Admin Only]")
def update_user(user_id: str, u: UserBase, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    res = user_service.update_user(db, user_id, u, current_user)
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.post("/me/kiss24-key", summary="Securely store personal KISS24 API Key")
def update_my_kiss24_key(payload: Kiss24KeyUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_service.update_my_kiss24_key(db, payload, current_user)


@router.get("/me/kiss24-key/validate", summary="Check if stored key is still valid")
def validate_stored_kiss24_key(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_service.validate_stored_kiss24_key(db, current_user)


@router.get("/me")
def get_my_profile(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_service.get_my_profile(db, current_user)


@router.get("/me/notifications")
def get_my_notifications(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_service.get_my_notifications(db, current_user)


@router.put("/me/notifications/read")
def mark_notifications_read(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_service.mark_notifications_read(db, current_user)


@router.get("/public-keys", summary="Get all users with configured public keys")
def get_user_public_keys(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_service.get_user_public_keys(db)


@router.post("/me/public-key", summary="Securely store personal E2EE Public Key")
def update_my_public_key(payload: PublicKeyUpdate, current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    return user_service.update_my_public_key(db, payload, current_user)