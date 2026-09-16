import uuid
from datetime import datetime
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import text, func, or_
from models.users import Users
from models.tests import Assignments
from models.notifications import Notifications
from audit_logger import log_audit_event
from utils.kiss24_service import verify_kiss24_api_key
from utils.security_cipher import get_cipher
from utils.timeaware import aware_utcnow


def check_system_status(db: Session):
    count = db.query(func.count(Users.id)).scalar()
    return {"setup_required": count == 0}


def get_system_time():
    now = datetime.now()
    iso = now.isocalendar()
    return {"year": iso[0], "week": iso[1]}


def get_all_users(db: Session):
    users = db.query(Users).order_by(Users.name.asc()).all()

    return [{
        "id": str(u.id), "email": u.email, "name": u.name, "role": u.role.value if hasattr(u.role, 'value') else u.role,
        "base_capacity": u.base_capacity, "start_week": u.start_week, "start_year": u.start_year,
        "end_week": u.end_week, "end_year": u.end_year, "location_id": str(u.location_id) if u.location_id else None,
        "kiss24_uuid": u.kiss24_uuid, "kiss24_api_key": u.kiss24_api_key,
        "service_lane_id": str(u.service_lane_id) if u.service_lane_id else None
    } for u in users]


def create_user(db: Session, u, current_user: dict):
    role_val = u.role.value if hasattr(u.role, 'value') else u.role
    if role_val in ['read_only', 'maintainer']:
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None
    loc_id = str(u.location_id) if u.location_id else None
    sl_id = str(u.service_lane_id) if u.service_lane_id else None
    new_user_id = str(uuid.uuid4())

    new_user = Users(
        id=new_user_id, email=u.email.lower(), name=u.name, role=role_val,
        location_id=loc_id, base_capacity=u.base_capacity, start_week=u.start_week,
        start_year=u.start_year, end_week=ew, end_year=ey, service_lane_id=sl_id
    )
    db.add(new_user)
    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="USER_CREATED",
        resource_type="USER", resource_id=str(new_user_id), details=f"User with ID: {new_user_id} was created."
    )
    return {"message": f"User {u.name} whitelisted in the database.", "id": new_user_id}


def delete_user(db: Session, user_id: str, current_user: dict):
    assign_count = db.query(func.count(Assignments.id)).filter(Assignments.user_id == user_id).scalar()

    # Safe fallback to text() for events in case the model is named differently
    event_count = db.execute(text("SELECT COUNT(*) FROM events WHERE user_id = :uid"), {"uid": user_id}).scalar()

    if assign_count == 0 and event_count == 0:
        db.query(Users).filter(Users.id == user_id).delete()
        db.commit()
        return {"message": "User permanently deleted."}
    else:
        current_year = datetime.now().year
        current_week = datetime.now().isocalendar()[1]

        user = db.query(Users).filter(Users.id == user_id).first()
        if user:
            user.end_year = current_year
            user.end_week = current_week
            db.commit()

        log_audit_event(
            user_id=str(current_user["id"]), role=current_user["role"], action="USER_DELETED",
            resource_type="USER", resource_id=str(user_id), details=f"User with ID: {user_id} was deleted."
        )
        return {"message": "User successfully offboarded."}


def update_user(db: Session, user_id: str, u, current_user: dict):
    role_val = u.role.value if hasattr(u.role, 'value') else u.role
    if role_val in ['read_only', 'maintainer']:
        u.base_capacity = 0.0

    ew = u.end_week if str(u.end_week).strip() != '' else None
    ey = u.end_year if str(u.end_year).strip() != '' else None
    loc_id = str(u.location_id) if u.location_id else None
    sl_id = str(u.service_lane_id) if u.service_lane_id else None

    user = db.query(Users).filter(Users.id == user_id).first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found.")

    old_role = str(user.role).strip().lower()
    new_role = str(role_val).strip().lower()

    if old_role != new_role:
        # Safe fallback for api_keys delete
        db.execute(text("DELETE FROM api_keys WHERE user_id = :uid"), {"uid": user_id})

        message = f"Your role was changed from '{old_role}' to '{new_role}'. For security reasons, all your active API keys have been revoked."
        db.add(Notifications(id=str(uuid.uuid4()), user_id=user_id, message=message, type='REMOVAL',
                             created_at=aware_utcnow()))

    user.name = u.name
    user.role = role_val
    user.location_id = loc_id
    user.base_capacity = u.base_capacity
    user.start_week = u.start_week
    user.start_year = u.start_year
    user.end_week = ew
    user.end_year = ey
    user.service_lane_id = sl_id

    db.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user["role"], action="USER_UPDATED",
        resource_type="USER", resource_id=str(user_id), details=f"User with ID: {user_id} was updated."
    )
    return {"message": "User updated."}


def update_my_kiss24_key(db: Session, payload, current_user: dict):
    clean_key = payload.api_key.strip()
    is_valid, msg = verify_kiss24_api_key(clean_key)

    if not is_valid:
        raise HTTPException(status_code=400, detail=f"Keep Secure 24 rejected this API Key: {msg}")

    cipher = get_cipher()
    encrypted_key = cipher.encrypt(clean_key.encode('utf-8')).decode('utf-8')

    user = db.query(Users).filter(Users.id == str(current_user["id"])).first()
    if user:
        user.kiss24_api_key = encrypted_key
        db.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user.get("role", "pentester"), action="KISS24_API_KEY_UPDATED",
        resource_type="USER", resource_id=str(current_user["id"]),
        details="User securely updated their Keep Secure 24 API key."
    )
    return {"message": "Keep Secure 24 API key validated and securely stored."}


def validate_stored_kiss24_key(db: Session, current_user: dict):
    user = db.query(Users).filter(Users.id == str(current_user["id"])).first()

    if not user or not user.kiss24_api_key:
        return {"is_valid": False, "message": "No API key configured."}

    cipher = get_cipher()
    try:
        decrypted_key = cipher.decrypt(user.kiss24_api_key.encode('utf-8')).decode('utf-8')
    except Exception:
        return {"is_valid": False, "message": "Failed to decrypt API key."}

    is_valid, msg = verify_kiss24_api_key(decrypted_key)
    return {"is_valid": is_valid, "message": msg}


def get_my_profile(db: Session, current_user: dict):
    user = db.query(Users).filter(Users.id == str(current_user["id"])).first()
    profile = dict(current_user)
    profile["has_kiss24_key"] = bool(user and user.kiss24_api_key)
    return profile


def get_my_notifications(db: Session, current_user: dict):
    notifs = db.query(Notifications).filter(
        Notifications.user_id == str(current_user['id']),
        or_(Notifications.is_read == False, Notifications.is_read.is_(None))
    ).order_by(Notifications.created_at.desc()).all()

    return [{"id": str(n.id), "message": n.message, "type": n.type, "created_at": n.created_at} for n in notifs]


def mark_notifications_read(db: Session, current_user: dict):
    db.query(Notifications).filter(Notifications.user_id == str(current_user['id'])).update({"is_read": True},
                                                                                            synchronize_session=False)
    db.commit()
    return {"message": "Notifications marked as read."}


def get_user_public_keys(db: Session):
    users = db.query(Users.id, Users.name, Users.public_key).filter(Users.end_year.is_(None)).all()
    return [{"id": str(u.id), "name": u.name, "public_key": u.public_key, "has_key": u.public_key is not None} for u in
            users]


def update_my_public_key(db: Session, payload, current_user: dict):
    if "PRIVATE KEY" in payload.public_key.upper():
        raise HTTPException(status_code=400,
                            detail="WARNING: You pasted a PRIVATE key! Never share this. Please upload the PUBLIC key.")

    user = db.query(Users).filter(Users.id == str(current_user["id"])).first()
    if user:
        user.public_key = payload.public_key.strip()
        db.commit()

    log_audit_event(
        user_id=str(current_user["id"]), role=current_user.get("role", "pentester"), action="E2EE_PUBLIC_KEY_UPDATED",
        resource_type="USER", resource_id=str(current_user["id"]),
        details="User generated and vaulted a new E2EE Public Key."
    )
    return {"message": "Public Key successfully linked to your account."}