import uuid
from datetime import datetime
from fastapi import HTTPException
from audit_logger import log_audit_event
from routers.auth import verify_lane_access


def get_services(cursor, year: int, current_user: dict):
    where_clauses = []
    params = [year]

    if current_user.get('role') == 'maintainer':
        lane_id = current_user.get('service_lane_id')
        if lane_id:
            where_clauses.append("sl.id = %s")
            params.append(str(lane_id))
        else:
            where_clauses.append("sl.id = '00000000-0000-0000-0000-000000000000'")

    where_str = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cursor.execute(f'''
        SELECT sl.id, sl.name, sl.max_concurrent_per_week, sl.theme_color, 
                sl.default_credits, sl.default_duration_weeks, sl.display_order, sl.is_active,
                sl.auto_provision_workspace, 
                sl.intro_email_template, sl.final_email_template, sl.requires_mitre, 
                COALESCE(slg.target_goal, 0) as target_goal
        FROM services_lanes sl
        LEFT JOIN service_lane_goals slg ON sl.id = slg.service_lane_id AND slg.year = %s
        {where_str}
        ORDER BY sl.display_order ASC, sl.name ASC
    ''', tuple(params))

    columns = [desc[0] for desc in cursor.description]
    services = [dict(zip(columns, row)) for row in cursor.fetchall()]

    for s in services:
        s['default_credits'] = float(s['default_credits'] or 2.0)
        s['default_duration_weeks'] = int(s['default_duration_weeks'] or 1)
        s['target_goal'] = int(s['target_goal'] or 0)

    return services


def create_service(cursor, s, year: int, current_user: dict):
    new_service_id = str(uuid.uuid4())
    cursor.execute(
        '''INSERT INTO services_lanes 
            (id, name, max_concurrent_per_week, theme_color, default_credits, default_duration_weeks, display_order, is_active, auto_provision_workspace, requires_mitre)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
           ON CONFLICT (name) DO UPDATE 
            SET is_active = EXCLUDED.is_active,
               max_concurrent_per_week = EXCLUDED.max_concurrent_per_week,
               theme_color = EXCLUDED.theme_color,
               default_credits = EXCLUDED.default_credits,
               default_duration_weeks = EXCLUDED.default_duration_weeks,
               display_order = EXCLUDED.display_order,
               auto_provision_workspace = EXCLUDED.auto_provision_workspace,
               requires_mitre = EXCLUDED.requires_mitre
           RETURNING id''',
        (new_service_id, s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits,
         s.default_duration_weeks, s.display_order, s.is_active, s.auto_provision_workspace, s.requires_mitre)
    )
    returned_id = cursor.fetchone()[0]

    cursor.execute('''
            INSERT INTO service_lane_goals (id, service_lane_id, year, target_goal)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (service_lane_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
        ''', (str(uuid.uuid4()), returned_id, year, s.target_goal))

    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SERVICES_LANES_CREATED",
        resource_type="SERVICES_LANES",
        resource_id=str(new_service_id),
        details=f"Service Lane {s.name} with ID: {new_service_id} was created."
    )
    return {"message": "Service lane created or restored", "id": new_service_id}


def update_service(cursor, service_id: str, s, year: int, current_user: dict):
    cursor.execute(
        '''UPDATE services_lanes 
            SET name=%s, max_concurrent_per_week=%s, theme_color=%s,
                default_credits=%s, default_duration_weeks=%s, display_order=%s, is_active=%s,
                auto_provision_workspace=%s, requires_mitre=%s
            WHERE id=%s''',
        (s.name, s.max_concurrent_per_week, s.theme_color, s.default_credits,
         s.default_duration_weeks, s.display_order, s.is_active, s.auto_provision_workspace, s.requires_mitre, service_id)
    )

    cursor.execute('''
        INSERT INTO service_lane_goals (id, service_lane_id, year, target_goal)
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (service_lane_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
    ''', (str(uuid.uuid4()), service_id, year, s.target_goal))

    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SERVICES_LANES_UPDATED",
        resource_type="SERVICES_LANES",
        resource_id=str(service_id),
        details=f"Service Lane  with ID: {service_id} was updated."
    )
    return {"message": "Service lane updated"}


def delete_service(cursor, service_id: str, current_user: dict):
    cursor.execute('DELETE FROM services_lanes WHERE id = %s', (service_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="SERVICES_LANES_DELETED",
        resource_type="SERVICES_LANES",
        resource_id=str(service_id),
        details=f"Service Lane  with ID: {service_id} was deleted."
    )
    return {"message": "Service lane deleted"}


def get_service_goals(cursor, service_id: str):
    cursor.execute("""
        SELECT year, target_goal 
        FROM service_lane_goals 
        WHERE service_lane_id = %s 
        ORDER BY year DESC
    """, (service_id,))
    return [{"year": r[0], "target_goal": r[1]} for r in cursor.fetchall()]


def set_service_goal(cursor, service_id: str, year: int, target_goal: int, current_user: dict):
    cursor.execute('''
        INSERT INTO service_lane_goals (id, service_lane_id, year, target_goal) 
        VALUES (%s, %s, %s, %s)
        ON CONFLICT (service_lane_id, year) DO UPDATE SET target_goal = EXCLUDED.target_goal
    ''', (str(uuid.uuid4()), service_id, year, target_goal))

    cursor.connection.commit()
    return {"message": f"Goal for {year} saved successfully."}


def create_placeholder(cursor, p, current_user: dict):
    new_placeholder_id = str(uuid.uuid4())
    default_credits = 2

    cursor.execute(
        '''INSERT INTO service_placeholders 
            (id, service_lane_id, year, week, credits)
            VALUES (%s, %s, %s, %s, %s)
           RETURNING id, service_lane_id, year, week, credits''',
        (new_placeholder_id, p.service_lane_id, p.year, p.week, default_credits)
    )
    row = cursor.fetchone()
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="PLACEHOLDER_CREATED",
        resource_type="SERVICE_PLACEHOLDERS",
        resource_id=new_placeholder_id,
        details=f"Placeholder created for service {p.service_lane_id} in week {p.week} of {p.year}."
    )

    columns = [desc[0] for desc in cursor.description]
    return dict(zip(columns, row))


def delete_placeholder(cursor, placeholder_id: str, current_user: dict):
    cursor.execute('DELETE FROM service_placeholders WHERE id = %s', (placeholder_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="PLACEHOLDER_DELETED",
        resource_type="SERVICE_PLACEHOLDERS",
        resource_id=placeholder_id,
        details=f"Placeholder {placeholder_id} was deleted."
    )
    return {"message": "Placeholder deleted"}


def update_service_lane_templates(cursor, service_lane_id: str, payload, current_user: dict):
    verify_lane_access(current_user, str(service_lane_id))

    cursor.execute("""
        UPDATE services_lanes
        SET intro_email_template = COALESCE(%s, intro_email_template),
            final_email_template = COALESCE(%s, final_email_template)
        WHERE id = %s
        RETURNING id;
    """, (payload.intro_email_template, payload.final_email_template, service_lane_id))

    updated_id = cursor.fetchone()
    if not updated_id:
        raise HTTPException(status_code=404, detail="Service Lane not found")

    cursor.connection.commit()
    return {"status": "Success", "message": "Templates updated successfully"}