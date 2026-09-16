import uuid
from sqlalchemy.orm import Session, joinedload
from models.contacts import Contacts, CountryContacts, RawAssetContacts
from audit_logger import log_audit_event


def upsert_global_contact(db: Session, email: str, full_name: str = None) -> str:
    """Helper to find an existing contact by email or create a new one."""
    email = email.lower().strip()

    contact = db.query(Contacts).filter(Contacts.email == email).first()

    if contact:
        if full_name:
            contact.full_name = full_name
            db.flush()  # Save the name change to the transaction without fully committing yet
        return str(contact.id)
    else:
        new_contact = Contacts(
            email=email,
            full_name=full_name
        )
        db.add(new_contact)
        db.flush()  # Flush to generate the new UUID so we can return it
        return str(new_contact.id)


def get_all_contacts(db: Session):
    """Fetches all contacts and aggregates their country and asset mappings."""
    # We use joinedload to eagerly fetch the mappings and their parent objects
    # to avoid the N+1 query problem, making this extremely fast!
    contacts = db.query(Contacts).options(
        joinedload(Contacts.country_mappings).joinedload(CountryContacts.country),
        joinedload(Contacts.raw_asset_mappings).joinedload(RawAssetContacts.raw_asset)
    ).order_by(Contacts.email.asc()).all()

    result = []
    for c in contacts:
        c_maps = [
            {
                "country_id": str(cm.country_id),
                "country_name": cm.country.name if cm.country else None,
                "is_stakeholder": cm.is_stakeholder,
                "is_developer": cm.is_developer
            } for cm in c.country_mappings
        ]

        a_maps = [
            {
                "raw_asset_id": str(am.raw_asset_id),
                "asset_name": am.raw_asset.name if am.raw_asset else None,
                "is_stakeholder": am.is_stakeholder,
                "is_developer": am.is_developer
            } for am in c.raw_asset_mappings
        ]

        result.append({
            "id": str(c.id),
            "email": c.email,
            "full_name": c.full_name,
            "country_mappings": c_maps,
            "asset_mappings": a_maps
        })

    return result


def sync_full_contact(db: Session, payload, current_user: dict):
    """Syncs a contact and completely rebuilds their country and asset mappings."""
    contact_id = upsert_global_contact(db, payload.email, payload.full_name)

    # 1. Sync Countries
    db.query(CountryContacts).filter(CountryContacts.contact_id == contact_id).delete()
    for c in payload.countries:
        new_country_mapping = CountryContacts(
            country_id=str(c.id),
            contact_id=contact_id,
            is_stakeholder=c.is_stakeholder,
            is_developer=c.is_developer
        )
        db.add(new_country_mapping)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="CONTACT_COUNTRY_ADD_EDIT",
            resource_type="CONTACTS",
            resource_id=str(contact_id),
            details=f"Contact with ID: {contact_id} has been added to country {c.id}.",
        )

    # 2. Sync Assets
    db.query(RawAssetContacts).filter(RawAssetContacts.contact_id == contact_id).delete()
    for a in payload.assets:
        new_asset_mapping = RawAssetContacts(
            raw_asset_id=str(a.id),
            contact_id=contact_id,
            is_stakeholder=a.is_stakeholder,
            is_developer=a.is_developer
        )
        db.add(new_asset_mapping)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="CONTACT_ASSET_ADD_EDIT",
            resource_type="CONTACTS",
            resource_id=str(contact_id),
            details=f"Contact with ID: {contact_id} has been added to asset {a.id}.",
        )

    db.commit()
    return {"message": "Contact and mappings synced successfully"}


def delete_global_contact(db: Session, contact_id: str, current_user: dict):
    """Permanently deletes a global contact."""
    contact = db.query(Contacts).filter(Contacts.id == contact_id).first()

    if contact:
        db.delete(contact)
        db.commit()

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="CONTACT_DELETED",
            resource_type="CONTACTS",
            resource_id=str(contact_id),
            details=f"Contact with ID: {contact_id} has been deleted.",
        )
    return {"message": "Global contact completely purged."}


def get_asset_contacts(db: Session, raw_asset_id: str):
    """Fetches all contacts linked to a specific raw asset."""
    mappings = (db.query(RawAssetContacts, Contacts)
                .join(Contacts, RawAssetContacts.contact_id == Contacts.id)
                .filter(RawAssetContacts.raw_asset_id == raw_asset_id)
                .order_by(Contacts.email.asc()).all())

    return [
        {
            "contact_id": str(contact.id),
            "mapping_id": str(mapping.id),
            "email": contact.email,
            "full_name": contact.full_name,
            "is_stakeholder": mapping.is_stakeholder,
            "is_developer": mapping.is_developer
        }
        for mapping, contact in mappings
    ]


def get_country_contacts(db: Session, country_id: str):
    """Fetches all contacts linked to a specific country."""
    mappings = (db.query(CountryContacts, Contacts)
                .join(Contacts, CountryContacts.contact_id == Contacts.id)
                .filter(CountryContacts.country_id == country_id)
                .order_by(Contacts.email.asc())
                .all())

    return [
        {
            "contact_id": str(contact.id),
            "mapping_id": str(mapping.id),
            "email": contact.email,
            "full_name": contact.full_name,
            "is_stakeholder": mapping.is_stakeholder,
            "is_developer": mapping.is_developer
        }
        for mapping, contact in mappings
    ]