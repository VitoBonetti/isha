from fastapi import APIRouter, Depends, Query
from typing import Optional
from database import get_db_cursor
from routers.auth import require_admin

router = APIRouter(prefix="/api/documents", tags=["Documents"])


@router.get("/", summary="[Admin Only] Get all test documents with metadata")
def get_all_documents(
        page: int = Query(1, ge=1),
        limit: int = Query(20, ge=1, le=100),
        search: Optional[str] = None,
        service_lane_id: Optional[str] = None,
        sort_by: str = Query("synced_at"),
        sort_dir: str = Query("desc"),
        current_user: dict = Depends(require_admin),
        cursor=Depends(get_db_cursor)
):
    offset = (page - 1) * limit

    base_query = """
        FROM test_documents td
        JOIN tests t ON td.test_id = t.id
        JOIN services_lanes sl ON t.service_lane_id = sl.id
        LEFT JOIN test_assets ta ON t.id = ta.test_id
        LEFT JOIN assets a ON ta.asset_id = a.id
        LEFT JOIN countries c ON a.country_id = c.id
    """

    where_clauses = []
    params = []

    if search:
        where_clauses.append("(td.file_name ILIKE %s OR t.name ILIKE %s)")
        params.extend([f"%{search}%", f"%{search}%"])

    if service_lane_id:
        where_clauses.append("t.service_lane_id = %s")
        params.append(service_lane_id)

    where_str = ""
    if where_clauses:
        where_str = "WHERE " + " AND ".join(where_clauses)

    # Ordering protection mapping
    valid_sort_cols = {
        "file_name": "td.file_name",
        "test_name": "t.name",
        "service": "sl.name",
        "synced_at": "td.synced_at",
        "scheduled": "t.start_year, t.start_week"
    }
    sort_col = valid_sort_cols.get(sort_by, "td.synced_at")
    dir_str = "ASC" if sort_dir.lower() == "asc" else "DESC"

    # Get total count for pagination
    count_query = f"SELECT COUNT(DISTINCT td.id) {base_query} {where_str}"
    cursor.execute(count_query, params)
    total_count = cursor.fetchone()[0]

    # Get paginated data (String_Agg combines multiple countries into one string!)
    data_query = f"""
        SELECT 
            td.id as doc_id,
            td.file_name,
            td.file_url,
            td.mime_type,
            td.synced_at,
            t.id as test_id,
            t.name as test_name,
            t.start_week,
            t.start_year,
            sl.name as service_name,
            STRING_AGG(DISTINCT c.code, ', ') as countries
        {base_query}
        {where_str}
        GROUP BY td.id, t.id, sl.id
        ORDER BY {sort_col} {dir_str}
        LIMIT %s OFFSET %s
    """
    cursor.execute(data_query, params + [limit, offset])
    rows = cursor.fetchall()

    columns = [desc[0] for desc in cursor.description]
    items = [dict(zip(columns, row)) for row in rows]

    return {
        "items": items,
        "total_count": total_count,
        "page": page,
        "limit": limit
    }