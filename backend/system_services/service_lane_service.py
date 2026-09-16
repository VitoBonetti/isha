import uuid
from fastapi import HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import and_
from sqlalchemy.dialects.postgresql import insert
from models.services import ServiceLanes, ServiceLaneGoals, ServicePlaceholders
from audit_logger import log_audit_event
from routers.auth import verify_lane_access


def get_services(db: Session, year: int, current_user: dict):
    query = db.query(ServiceLanes, ServiceLaneGoals.target_goal) \
        .outerjoin(ServiceLaneGoals,
                   and_(ServiceLanes.id == ServiceLaneGoals.service_lane_id, ServiceLaneGoals.year == year))

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        if lane_id:
            query = query.filter(ServiceLanes.id == str(lane_id))
        else:
            # Fallback if maintainer has no lane assigned
            query = query.filter(ServiceLanes.id == '00000000-0000-0000-0000-000000000000')

    query = query.order_by(ServiceLanes.display_order.asc(), ServiceLanes.name.asc())

    results = []
    for lane, target_goal in query.all():
        results.append({
            "id": str(lane.id),
            "name": lane.name,
            "max_concurrent_per_week": lane.max_concurrent_per_week,
            "theme_color": lane.theme_color,
            "default_credits": float(lane.default_credits or 2.0),
            "default_duration_weeks": int(lane.default_duration_weeks or 1),
            "display_order": lane.display_order,
            "is_active": lane.is_active,
            "auto_provision_workspace": lane.auto_provision_workspace,
            "intro_email_template": lane.intro_email_template,
            "final_email_template": lane.final_email_template,
            "requires_mitre": lane.requires_mitre,
            "target_goal": int(target_goal or 0)
        })

    return results


def create_service(db: Session, s, year: int, current_user: dict):
    new_service_id = str(uuid.uuid4())

    # 1. Upsert Service Lane
    stmt_lane = insert(ServiceLanes).values(
        id=new_service_id, name=s.name, max_concurrent_per_week=s.max_concurrent_per_week,
        theme_color=s.theme_color, default_credits=s.default_credits,
        default_duration_weeks=s.default_duration_weeks, display_order=s.display_order,
        is_active=s.is_active, auto_provision_workspace=s.auto_provision_workspace,
        requires_mitre=s.requires_mitre
    ).on_conflict_do_update(
        index_elements=['name'],
        set_={
            'is_active': s.is_active, 'max_concurrent_per_week': s.max_concurrent_per_week,
            'theme_color': s.theme_color, 'default_credits': s.default_credits,
            'default_duration_weeks': s.default_duration_weeks, 'display_order': s.display_order,
            'auto_provision_workspace': s.auto_provision_workspace, 'requires_mitre': s.requires_mitre
        }
    ).returning(ServiceLanes.id)

    returned_id = db.execute(stmt_lane).scalar()

    # 2. Upsert Service Goal
    stmt_goal = insert(ServiceLaneGoals).values(
        id=str(uuid.uuid4()), service_lane_id=returned_id, year=year, target_goal=s.target_goal
    ).on_conflict_do_update(
        index_elements=['service_lane_id', 'year'],
        set_={'target_goal': s.target_goal}
    )
    db.execute(stmt_goal)
    db.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "SERVICES_LANES_CREATED", "SERVICES_LANES",
                    str(new_service_id), f"Service Lane {s.name} with ID: {new_service_id} was created.")
    return {"message": "Service lane created or restored", "id": new_service_id}


def update_service(db: Session, service_id: str, s, year: int, current_user: dict):
    lane = db.query(ServiceLanes).filter(ServiceLanes.id == service_id).first()
    if lane:
        lane.name = s.name
        lane.max_concurrent_per_week = s.max_concurrent_per_week
        lane.theme_color = s.theme_color
        lane.default_credits = s.default_credits
        lane.default_duration_weeks = s.default_duration_weeks
        lane.display_order = s.display_order
        lane.is_active = s.is_active
        lane.auto_provision_workspace = s.auto_provision_workspace
        lane.requires_mitre = s.requires_mitre

    stmt_goal = insert(ServiceLaneGoals).values(
        id=str(uuid.uuid4()), service_lane_id=service_id, year=year, target_goal=s.target_goal
    ).on_conflict_do_update(
        index_elements=['service_lane_id', 'year'],
        set_={'target_goal': s.target_goal}
    )
    db.execute(stmt_goal)
    db.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "SERVICES_LANES_UPDATED", "SERVICES_LANES",
                    str(service_id), f"Service Lane with ID: {service_id} was updated.")
    return {"message": "Service lane updated"}


def delete_service(db: Session, service_id: str, current_user: dict):
    db.query(ServiceLanes).filter(ServiceLanes.id == service_id).delete()
    db.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "SERVICES_LANES_DELETED", "SERVICES_LANES",
                    str(service_id), f"Service Lane with ID: {service_id} was deleted.")
    return {"message": "Service lane deleted"}


def get_service_goals(db: Session, service_id: str):
    goals = db.query(ServiceLaneGoals).filter(ServiceLaneGoals.service_lane_id == service_id).order_by(
        ServiceLaneGoals.year.desc()).all()
    return [{"year": g.year, "target_goal": g.target_goal} for g in goals]


def set_service_goal(db: Session, service_id: str, year: int, target_goal: int, current_user: dict):
    stmt = insert(ServiceLaneGoals).values(
        id=str(uuid.uuid4()), service_lane_id=service_id, year=year, target_goal=target_goal
    ).on_conflict_do_update(
        index_elements=['service_lane_id', 'year'],
        set_={'target_goal': target_goal}
    )
    db.execute(stmt)
    db.commit()
    return {"message": f"Goal for {year} saved successfully."}


def create_placeholder(db: Session, p, current_user: dict):
    new_ph = ServicePlaceholders(
        id=str(uuid.uuid4()),
        service_lane_id=p.service_lane_id,
        year=p.year,
        week=p.week,
        credits=2.0
    )
    db.add(new_ph)
    db.commit()
    db.refresh(new_ph)

    log_audit_event(str(current_user["id"]), current_user["role"], "PLACEHOLDER_CREATED", "SERVICE_PLACEHOLDERS",
                    str(new_ph.id),
                    f"Placeholder created for service {p.service_lane_id} in week {p.week} of {p.year}.")
    return {"id": str(new_ph.id), "service_lane_id": str(new_ph.service_lane_id), "year": new_ph.year,
            "week": new_ph.week, "credits": new_ph.credits}


def delete_placeholder(db: Session, placeholder_id: str, current_user: dict):
    db.query(ServicePlaceholders).filter(ServicePlaceholders.id == placeholder_id).delete()
    db.commit()

    log_audit_event(str(current_user["id"]), current_user["role"], "PLACEHOLDER_DELETED", "SERVICE_PLACEHOLDERS",
                    placeholder_id, f"Placeholder {placeholder_id} was deleted.")
    return {"message": "Placeholder deleted"}


def update_service_lane_templates(db: Session, service_lane_id: str, payload, current_user: dict):
    verify_lane_access(current_user, str(service_lane_id))

    lane = db.query(ServiceLanes).filter(ServiceLanes.id == service_lane_id).first()
    if not lane:
        raise HTTPException(status_code=404, detail="Service Lane not found")

    if payload.intro_email_template is not None:
        lane.intro_email_template = payload.intro_email_template
    if payload.final_email_template is not None:
        lane.final_email_template = payload.final_email_template

    db.commit()
    return {"status": "Success", "message": "Templates updated successfully"}