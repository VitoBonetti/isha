from fastapi import APIRouter, Depends, HTTPException
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
from models import CountryBase

router = APIRouter(prefix="/api/countries", tags=["Countries"])


@router.get("/")
def get_countries(current_user: dict = Depends(get_current_user), cursor=Depends(get_db_cursor)):
    if current_user.get('role') == 'pentester':
        raise HTTPException(status_code=403, detail="Pentesters cannot access country data.")

    cursor.execute("SELECT id, code, name, is_active FROM countries ORDER BY code")
    return [{"id": r[0], "code": r[1], "name": r[2], "is_active": r[3]} for r in cursor.fetchall()]


@router.post("/")
def create_country(c: CountryBase, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    try:
        cursor.execute(
            "INSERT INTO countries (code, name, is_active) VALUES (%s, %s, %s) RETURNING id",
            (c.code, c.name, c.is_active)
        )
        new_id = cursor.fetchone()[0]
        cursor.connection.commit()
        return {"id": new_id, "message": "Country created successfully."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=400, detail="Database error (Code might already exist)")


@router.put("/{country_id}")
def update_country(country_id: str, c: CountryBase, current_user: dict = Depends(require_admin),
                   cursor=Depends(get_db_cursor)):
    cursor.execute(
        "UPDATE countries SET code=%s, name=%s, is_active=%s WHERE id=%s",
        (c.code, c.name, c.is_active, country_id)
    )
    cursor.connection.commit()
    return {"message": "Country updated successfully."}


@router.delete("/{country_id}")
def delete_country(country_id: str, current_user: dict = Depends(require_admin), cursor=Depends(get_db_cursor)):
    cursor.execute("DELETE FROM countries WHERE id = %s", (country_id,))
    cursor.connection.commit()
    return {"message": "Country deleted."}


@router.get("/{country_id}/analytics")
def get_country_analytics(country_id: str, current_user: dict = Depends(get_current_user),
                          cursor=Depends(get_db_cursor)):
    """Aggregates active pool statistics mapped to dynamic service lanes."""

    # 1. Get raw vs active pool counts
    cursor.execute("SELECT COUNT(*) FROM raw_assets WHERE country_id = %s", (country_id,))
    total_raw = cursor.fetchone()[0]

    cursor.execute("SELECT COUNT(*) FROM assets WHERE country_id = %s", (country_id,))
    total_in_pool = cursor.fetchone()[0]

    # 2. Service Lane Breakdown for assets in the Active Pool
    cursor.execute("""
        SELECT COALESCE(s.name, 'Unassigned'), COUNT(a.id)
        FROM assets a
        LEFT JOIN service_lanes s ON a.service_forecast_id = s.id
        WHERE a.country_id = %s
        GROUP BY s.name
    """, (country_id,))
    service_breakdown = [{"service": r[0], "count": r[1]} for r in cursor.fetchall()]

    return {
        "total_raw_assets": total_raw,
        "total_assets_in_pool": total_in_pool,
        "service_breakdown": service_breakdown
    }