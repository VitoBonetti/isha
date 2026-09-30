from fastapi import APIRouter, Depends, BackgroundTasks
from database import get_db
from sqlalchemy.orm import Session
from routers.auth import get_current_user, require_admin, require_admin_or_read_only
from schema import UserCreate, UserBase, Kiss24KeyUpdate, PublicKeyUpdate
from websockets_manager import manager
from system_services import user_service
from utils.memory_cache import invalidate_board_cache

router = APIRouter(prefix="/api/users", tags=["Users"])


@router.get(
    "/system/status",
    summary="Check System Status"
)
def check_system_status(current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Verify the operational status of the core backend.

    A basic health-check endpoint confirming that the API and the relational database are actively communicating.
    """
    return user_service.check_system_status(db)


@router.get(
    "/system/time",
    summary="Get Server Time"
)
def get_system_time(current_user: dict = Depends(get_current_user)):
    """
    Retrieve the current UTC server time.

    Used to validate client clock offsets and synchronize token expirations.
    """
    return user_service.get_system_time()


@router.get(
    "/",
    summary="[Admin/ReadOnly] Get All Users"
)
def get_all_users(current_user: dict = Depends(require_admin_or_read_only), db: Session = Depends(get_db)):
    """
    Retrieve a list of all registered platform users.

    Fetches the comprehensive user directory including roles, email identifiers,
    and service lane assignments.
    """
    return user_service.get_all_users(db)


@router.post(
    "/",
    summary="[Admin Only] Create User"
)
def create_user(u: UserCreate, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                db: Session = Depends(get_db)):
    """
    Provision a new internal user account.

    Creates a new user profile, setting their access roles and optionally scoping
    them to specific geographic locations or testing lanes.
    """
    res = user_service.create_user(db, u, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.delete(
    "/{user_id}",
    summary="[Admin Only] Delete User"
)
def delete_user(user_id: str, background_tasks: BackgroundTasks, current_user: dict = Depends(require_admin),
                db: Session = Depends(get_db)):
    """
    Permanently delete a user account from the platform.

    Wipes the user profile and their associated active session keys. Will gracefully fail
    if the user is actively assigned to tests to prevent database inconsistencies.
    """
    res = user_service.delete_user(db, user_id, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.put(
    "/{user_id}",
    summary="[Admin Only] Update User"
)
def update_user(user_id: str, u: UserBase, background_tasks: BackgroundTasks,
                current_user: dict = Depends(require_admin), db: Session = Depends(get_db)):
    """
    Modify an existing user's details and role permissions.
    """
    res = user_service.update_user(db, user_id, u, current_user)
    invalidate_board_cache()
    background_tasks.add_task(manager.broadcast, '{"action": "REFRESH_BOARD"}')
    return res


@router.post(
    "/me/kiss24-key",
    summary="Update Personal KISS24 Key"
)
def update_my_kiss24_key(payload: Kiss24KeyUpdate, current_user: dict = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """
    Securely store or update the authenticated user's personal Keep Secure 24 API key.

    This key enables the backend to impersonate the user in KISS24 for executing actions
    like automated test provisioning and vulnerability publishing.
    """
    return user_service.update_my_kiss24_key(db, payload, current_user)


@router.get(
    "/me/kiss24-key/validate",
    summary="Validate Personal KISS24 Key"
)
def validate_stored_kiss24_key(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Check if the currently stored KISS24 API key is valid and active.

    Pings the KISS24 authentication endpoint with the stored key to verify it has not
    expired or been revoked.
    """
    return user_service.validate_stored_kiss24_key(db, current_user)


@router.get(
    "/me",
    summary="Get My Profile"
)
def get_my_profile(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the authenticated user's profile and configuration details.

    Returns standard identity metrics along with statuses indicating whether they
    have published a PGP/Public Key and a valid KISS24 API Token.
    """
    return user_service.get_my_profile(db, current_user)


@router.get(
    "/me/notifications",
    summary="Get My Notifications"
)
def get_my_notifications(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Retrieve the authenticated user's active system notifications.

    Fetches read and unread alerts pertinent to the user (e.g., API key expirations,
    assignment updates).
    """
    return user_service.get_my_notifications(db, current_user)


@router.put(
    "/me/notifications/read",
    summary="Mark Notifications Read"
)
def mark_notifications_read(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Acknowledge and mark all unread notifications as 'Read' for the authenticated user.
    """
    return user_service.mark_notifications_read(db, current_user)


@router.get(
    "/public-keys",
    summary="Get User Public Keys"
)
def get_user_public_keys(current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)):
    """
    Fetch a directory of all users who have published an E2EE public key.

    Allows client-side applications to encrypt data targeting specific recipients
    before sending it to the backend.
    """
    return user_service.get_user_public_keys(db)


@router.post(
    "/me/public-key",
    summary="Update Personal Public Key"
)
def update_my_public_key(payload: PublicKeyUpdate, current_user: dict = Depends(get_current_user),
                         db: Session = Depends(get_db)):
    """
    Securely store the authenticated user's End-to-End Encryption (E2EE) public key.

    Accepts PGP or generic public keys used by the frontend for securely passing
    encrypted credential notes inside the vault.
    """
    return user_service.update_my_public_key(db, payload, current_user)