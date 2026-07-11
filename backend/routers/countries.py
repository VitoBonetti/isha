from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, UUID4
from typing import Optional
from database import get_db_cursor
from routers.auth import get_current_user, require_admin
from schema import CountryBase
import uuid
from datetime import datetime


router = APIRouter(prefix="/api/countries", tags=["Countries"])


@router.get("/")
def get_countries(current_user: dict = Depends(get_current_user), cursor = Depends(get_db_cursor)):
    if current_user.get('role') == 'pentester':
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Pentesters cannot access country data.")

    cursor.execute("""
        SELECT c.id, c.code, c.name, c.is_active, c.region_id, r.name as region_name 
        FROM countries c 
        LEFT JOIN regions r ON c.region_id = r.id 
        ORDER BY c.code
    """)
    return [{"id": r[0], "code": r[1], "name": r[2], "is_active": r[3], "region_id": r[4], "region_name": r[5]} for r in cursor.fetchall()]

@router.post("/", summary="[Admin Only]")
def create_country(c: CountryBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    reg_id = str(c.region_id) if c.region_id else None
    new_country_id = str(uuid.uuid4())
    try:
        cursor.execute(
            "INSERT INTO countries (id, code, name, region_id, is_active) VALUES (%s, %s, %s, %s, %s)",
            (new_country_id, c.code, c.name, reg_id, c.is_active)
        )
        cursor.connection.commit()
        return {"id": new_country_id, "message": "Country created successfully."}
    except Exception as e:
        cursor.connection.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Database error (Code might already exist)")

@router.put("/{country_id}", summary="[Admin Only]")
def update_country(country_id: str, c: CountryBase, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    cursor.execute(
        "UPDATE countries SET code=%s, name=%s, region_id=%s, is_active=%s WHERE id=%s",
        (c.code, c.name, c.region_id, c.is_active, country_id)
    )
    cursor.connection.commit()
    return {"message": "Country updated successfully."}

@router.delete("/{country_id}", summary="[Admin Only]")
def delete_country(country_id: str, current_user: dict = Depends(require_admin), cursor = Depends(get_db_cursor)):
    cursor.execute("DELETE FROM countries WHERE id = %s", (country_id,))
    cursor.connection.commit()
    return {"message": "Country deleted."}


@router.get("/analytics", summary="[Admin Only]")
def get_country_analytics(year: Optional[int] = None, current_user: dict = Depends(require_admin),
                          cursor=Depends(get_db_cursor)):
    if not year:
        year = datetime.now().year

    # Massive Aggregation Query!
    cursor.execute("""
        SELECT 
            c.id, c.code, c.name, r.name as region_name,
            -- 1. Total Raw Assets linked to this country
            (SELECT COUNT(*) FROM raw_assets ra WHERE ra.country_id = c.id) as raw_assets_count,

            -- 2. Assets currently in the Active Pool
            (SELECT COUNT(*) FROM assets a 
             JOIN raw_assets ra ON a.raw_asset_id = ra.id 
             WHERE ra.country_id = c.id) as pool_assets_count,

            -- 3. Tests Completed IN THIS SPECIFIC YEAR
            (SELECT COUNT(*) FROM test_assets ta
             JOIN tests t ON ta.test_id = t.id
             JOIN assets a ON ta.asset_id = a.id
             JOIN raw_assets ra ON a.raw_asset_id = ra.id
             WHERE ra.country_id = c.id 
               AND t.stages::text = 'COMPLETED' 
               AND t.start_year = %s) as completed_tests_count,

            -- 4. Tests Scheduled/In Progress IN THIS SPECIFIC YEAR
            (SELECT COUNT(*) FROM test_assets ta
             JOIN tests t ON ta.test_id = t.id
             JOIN assets a ON ta.asset_id = a.id
             JOIN raw_assets ra ON a.raw_asset_id = ra.id
             WHERE ra.country_id = c.id 
               AND t.stages::text IN ('SCHEDULED', 'IN_PROGRESS') 
               AND t.start_year = %s) as active_tests_count

        FROM countries c
        LEFT JOIN regions r ON c.region_id = r.id
        WHERE c.is_active = TRUE
        ORDER BY completed_tests_count DESC, pool_assets_count DESC, c.name ASC
    """, (year, year))

    columns = [col[0] for col in cursor.description]
    return [dict(zip(columns, row)) for row in cursor.fetchall()]