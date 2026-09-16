import uuid
from audit_logger import log_audit_event


def upsert_global_contact(cursor, email: str, full_name: str = None) -> str:
    """Helper to find an existing contact by email or create a new one."""
    email = email.lower().strip()
    cursor.execute("SELECT id FROM contacts WHERE email = %s", (email,))
    row = cursor.fetchone()
    if row:
        contact_id = str(row[0])
        if full_name:
            cursor.execute("UPDATE contacts SET full_name = %s WHERE id = %s", (full_name, contact_id))
        return contact_id
    else:
        contact_id = str(uuid.uuid4())
        cursor.execute("INSERT INTO contacts (id, email, full_name) VALUES (%s, %s, %s)",
                       (contact_id, email, full_name))
        return contact_id


def get_all_contacts(cursor):
    """Fetches all contacts and aggregates their country and asset mappings into JSON arrays."""
    cursor.execute("""
        SELECT 
            c.id, c.email, c.full_name,
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'country_id', cc.country_id, 'country_name', co.name, 
                        'is_stakeholder', cc.is_stakeholder, 'is_developer', cc.is_developer
                    )
                ) FILTER (WHERE cc.id IS NOT NULL), '[]'
            ) as country_mappings,
            COALESCE(
                json_agg(
                    DISTINCT jsonb_build_object(
                        'raw_asset_id', rac.raw_asset_id, 'asset_name', ra.name, 
                        'is_stakeholder', rac.is_stakeholder, 'is_developer', rac.is_developer
                    )
                ) FILTER (WHERE rac.id IS NOT NULL), '[]'
            ) as asset_mappings
        FROM contacts c
        LEFT JOIN country_contacts cc ON c.id = cc.contact_id
        LEFT JOIN countries co ON cc.country_id = co.id
        LEFT JOIN raw_asset_contacts rac ON c.id = rac.contact_id
        LEFT JOIN raw_assets ra ON rac.raw_asset_id = ra.id
        GROUP BY c.id
        ORDER BY c.email ASC
    """)
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def sync_full_contact(cursor, payload, current_user: dict):
    """Syncs a contact and completely rebuilds their country and asset mappings."""
    contact_id = upsert_global_contact(cursor, payload.email, payload.full_name)

    # Sync Countries
    cursor.execute("DELETE FROM country_contacts WHERE contact_id = %s", (contact_id,))
    for c in payload.countries:
        cursor.execute("""
            INSERT INTO country_contacts (id, country_id, contact_id, is_stakeholder, is_developer)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), c.id, contact_id, c.is_stakeholder, c.is_developer))

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="CONTACT_COUNTRY_ADD_EDIT",
            resource_type="CONTACTS",
            resource_id=str(contact_id),
            details=f"Contacts with ID: {contact_id} has been add to country {c.id}.",
        )

    # Sync Assets
    cursor.execute("DELETE FROM raw_asset_contacts WHERE contact_id = %s", (contact_id,))
    for a in payload.assets:
        cursor.execute("""
            INSERT INTO raw_asset_contacts (id, raw_asset_id, contact_id, is_stakeholder, is_developer)
            VALUES (%s, %s, %s, %s, %s)
        """, (str(uuid.uuid4()), a.id, contact_id, a.is_stakeholder, a.is_developer))

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="CONTACT_ASSET_ADD_EDIT",
            resource_type="CONTACTS",
            resource_id=str(contact_id),
            details=f"Contacts with ID: {contact_id} has been add to asset {a.id}.",
        )

    cursor.connection.commit()
    return {"message": "Contact and mappings synced successfully"}


def delete_global_contact(cursor, contact_id: str, current_user: dict):
    """Permanently deletes a global contact."""
    cursor.execute("DELETE FROM contacts WHERE id = %s", (contact_id,))
    cursor.connection.commit()

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="CONTACT_DELETED",
        resource_type="CONTACTS",
        resource_id=str(contact_id),
        details=f"Contacts with ID: {contact_id} has been deleted.",
    )
    return {"message": "Global contact completely purged."}


def get_asset_contacts(cursor, raw_asset_id: str):
    """Fetches all contacts linked to a specific raw asset."""
    cursor.execute("""
        SELECT c.id as contact_id, rac.id as mapping_id, c.email, c.full_name, 
               rac.is_stakeholder, rac.is_developer
        FROM raw_asset_contacts rac
        JOIN contacts c ON rac.contact_id = c.id
        WHERE rac.raw_asset_id = %s
        ORDER BY c.email ASC
    """, (raw_asset_id,))
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]


def get_country_contacts(cursor, country_id: str):
    """Fetches all contacts linked to a specific country."""
    cursor.execute("""
        SELECT c.id as contact_id, cc.id as mapping_id, c.email, c.full_name, 
               cc.is_stakeholder, cc.is_developer
        FROM country_contacts cc
        JOIN contacts c ON cc.contact_id = c.id
        WHERE cc.country_id = %s
        ORDER BY c.email ASC
    """, (country_id,))
    columns = [desc[0] for desc in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]
