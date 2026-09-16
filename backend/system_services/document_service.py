from sqlalchemy.orm import Session
from sqlalchemy import func, or_
from models.tests import TestDocuments, Tests, TestAssets
from models.services import ServiceLanes
from models.assets import Assets
from models.territories import Country


def get_all_documents(db: Session, page: int, limit: int, search: str, service_lane_id: str, doc_type: str, sort_by: str, sort_dir: str):
    offset = (page - 1) * limit

    # --- BASE QUERY WITH JOINS ---
    query = (db.query(
        TestDocuments.id.label("doc_id"),
        TestDocuments.file_name,
        TestDocuments.file_url,
        TestDocuments.mime_type,
        TestDocuments.doc_type,
        TestDocuments.synced_at,
        Tests.id.label("test_id"),
        Tests.name.label("test_name"),
        Tests.start_week,
        Tests.start_year,
        ServiceLanes.name.label("service_name"),
        func.string_agg(func.distinct(Country.code), ', ').label("countries"))
             .outerjoin(Tests, TestDocuments.test_id == Tests.id)
             .outerjoin(ServiceLanes, Tests.service_lane_id == ServiceLanes.id)
             .outerjoin(TestAssets, Tests.id == TestAssets.test_id)
             .outerjoin(Assets, TestAssets.asset_id == Assets.id)
             .outerjoin(Country, Assets.country_id == Country.id))

    # --- DYNAMIC FILTERS ---
    if search:
        query = query.filter(
            or_(
                TestDocuments.file_name.ilike(f"%{search}%"),
                Tests.name.ilike(f"%{search}%")
            )
        )

    # Service Lane & Knowledge Base Scope Filter
    if service_lane_id == "kb_only":
        query = query.filter(TestDocuments.test_id.is_(None))
    elif service_lane_id == "all_incl_kb":
        pass  # Include everything
    elif service_lane_id and service_lane_id != "exclude_kb":
        query = query.filter(Tests.service_lane_id == service_lane_id)
    else:
        # Default behavior: Exclude Knowledge Base documents on initial load
        query = query.filter(TestDocuments.test_id.isnot(None))

    # Document Type Filter
    if doc_type:
        query = query.filter(TestDocuments.doc_type == doc_type)

    # --- GET TOTAL COUNT (Before grouping/limiting) ---
    total_count = query.with_entities(func.count(func.distinct(TestDocuments.id))).scalar() or 0

    # --- GROUPING ---
    query = query.group_by(
        TestDocuments.id,
        Tests.id,
        ServiceLanes.id
    )

    # --- SORTING ---
    valid_sort_cols = {
        "file_name": TestDocuments.file_name,
        "test_name": Tests.name,
        "service": ServiceLanes.name,
        "synced_at": TestDocuments.synced_at
    }

    if sort_by == "scheduled":
        # Special multi-column sort for schedule
        if sort_dir.lower() == "asc":
            query = query.order_by(Tests.start_year.asc().nullslast(), Tests.start_week.asc().nullslast())
        else:
            query = query.order_by(Tests.start_year.desc().nullslast(), Tests.start_week.desc().nullslast())
    else:
        sort_col = valid_sort_cols.get(sort_by, TestDocuments.synced_at)
        order_col = sort_col.asc().nullslast() if sort_dir.lower() == "asc" else sort_col.desc().nullslast()
        query = query.order_by(order_col)

    # --- PAGINATION & FETCH ---
    rows = query.offset(offset).limit(limit).all()

    # --- FORMAT RESULTS ---
    items = [{
        "doc_id": str(r.doc_id),
        "file_name": r.file_name,
        "file_url": r.file_url,
        "mime_type": r.mime_type,
        "doc_type": r.doc_type,
        "synced_at": r.synced_at,
        "test_id": str(r.test_id) if r.test_id else None,
        "test_name": r.test_name,
        "start_week": r.start_week,
        "start_year": r.start_year,
        "service_name": r.service_name,
        "countries": r.countries
    } for r in rows]

    return {
        "items": items,
        "total_count": total_count,
        "page": page,
        "limit": limit
    }