import os
import io
import pandas as pd
import math
from datetime import datetime, timezone
from google.cloud import storage
from sqlalchemy.orm import Session
from sqlalchemy.dialects.postgresql import insert
from fastapi import HTTPException
from database import SessionLocal
from models.tests import TestRitms
from audit_logger import log_audit_event, get_bq_client, TABLE_REF
from utils.timeaware import aware_utcnow

# --- Constants & Mappings ---
RITM_BUCKET_NAME = os.environ.get("RITM_BUCKET_NAME")
ARCHIVE_FOLDER = os.environ.get("RITM_BUCKET_ARCHIVE_FOLDER_NAME")

COLUMN_MAPPING = {
    "Number": "id",
    "Stage": "stage",
    "Short description": "description",
    "Requested for": "requested_by",
    "Company": "company",
    "Created": "created",
    "1. OneTrust Asset ID": "onetrust_id",
    "2. Name of the application": "name_app",
    "5. Please provide an estimated date on when you want the pentest to start": "estimated_date",
    "State": "state",
    "Closed": "closed",
    "Closed by": "closed_by",
    "Service Type": "service_requested"
}


# Helpers
def clean_string(val):
    """Strips leading/trailing spaces and converts nan/empty to None."""
    if pd.isna(val) or val == "":
        return None
    if isinstance(val, str):
        cleaned = val.strip()
        return cleaned if cleaned else None
    return val


def parse_datetime(val):
    """Parses standard date times, returns None if empty or invalid."""
    if pd.isna(val) or val == "" or str(val).strip() == "":
        return None
    try:
        # Pandas to_datetime handles variations well, we force UTC
        dt = pd.to_datetime(val)
        return dt.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def parse_date(val):
    """Parses date-only fields, returns None if empty or invalid."""
    dt = parse_datetime(val)
    if dt:
        return dt.date()
    return None


# Caller
def process_ritm_sync_background(user_id: str, user_role: str):
    """
    Background worker:
    1. Finds the latest RITM Excel sheet in GCS.
    2. Parses and cleans data using Pandas.
    3. Upserts data to PostgreSQL.
    4. Moves the file to the archive folder.
    """
    if not RITM_BUCKET_NAME:
        log_audit_event(user_id, user_role, "RITM_SYNC_FAILED", "SNOW_RITMS", "N/A", "RITM_BUCKET_NAME is not set.")
        return

    client = storage.Client()
    try:
        bucket = client.bucket(RITM_BUCKET_NAME)

        # 1. Find the latest file
        blobs = list(bucket.list_blobs())
        target_blobs = [
            b for b in blobs
            if b.name.startswith("ritm_")
               and b.name.endswith(".xlsx")
               and not b.name.startswith(f"{ARCHIVE_FOLDER}/")
        ]

        if not target_blobs:
            log_audit_event(user_id, user_role, "RITM_SYNC_SKIPPED", "SNOW_RITMS", "N/A",
                            "No new RITM sheets found in bucket.")
            return

        # Sort by name descending (since the timestamp/unicode is in the filename)
        target_blobs.sort(key=lambda x: x.name, reverse=True)
        latest_blob = target_blobs[0]

        # 2. Download and Parse with Pandas
        file_bytes = latest_blob.download_as_bytes()
        df = pd.read_excel(io.BytesIO(file_bytes))

        # Verify required columns exist
        missing_cols = [col for col in COLUMN_MAPPING.keys() if col not in df.columns]
        if missing_cols:
            log_audit_event(user_id, user_role, "RITM_SYNC_FAILED", "SNOW_RITMS", latest_blob.name,
                            f"Missing expected columns: {missing_cols}")
            return

        # Filter only the columns we need and rename them to match our DB schema
        df = df[list(COLUMN_MAPPING.keys())].rename(columns=COLUMN_MAPPING)

        # 3. Clean the data
        records_to_upsert = []
        for _, row in df.iterrows():
            record = {
                "id": clean_string(row.get("id")),
                "stage": clean_string(row.get("stage")),
                "description": clean_string(row.get("description")),
                "requested_by": clean_string(row.get("requested_by")),
                "company": clean_string(row.get("company")),
                "created": parse_datetime(row.get("created")),
                "onetrust_id": clean_string(row.get("onetrust_id")),
                "name_app": clean_string(row.get("name_app")),
                "estimated_date": parse_date(row.get("estimated_date")),
                "state": clean_string(row.get("state")),
                "closed": parse_datetime(row.get("closed")),
                "closed_by": clean_string(row.get("closed_by")),
                "service_requested": clean_string(row.get("service_requested")),
            }
            # Skip if primary key is completely missing
            if record["id"]:
                records_to_upsert.append(record)

        # 4. Upsert into Database
        db = SessionLocal()
        try:
            if records_to_upsert:
                stmt = insert(TestRitms).values(records_to_upsert)

                # Define ON CONFLICT DO UPDATE behavior
                stmt = stmt.on_conflict_do_update(
                    index_elements=['id'],
                    set_={
                        'stage': stmt.excluded.stage,
                        'description': stmt.excluded.description,
                        'requested_by': stmt.excluded.requested_by,
                        'company': stmt.excluded.company,
                        'created': stmt.excluded.created,
                        'onetrust_id': stmt.excluded.onetrust_id,
                        'name_app': stmt.excluded.name_app,
                        'estimated_date': stmt.excluded.estimated_date,
                        'state': stmt.excluded.state,
                        'closed': stmt.excluded.closed,
                        'closed_by': stmt.excluded.closed_by,
                        'service_requested': stmt.excluded.service_requested,
                    }
                )
                db.execute(stmt)
                db.commit()

            log_audit_event(user_id, user_role, "RITM_SYNC_SUCCESS", "SNOW_RITMS", latest_blob.name,
                            f"Successfully upserted {len(records_to_upsert)} RITMs.")

        except Exception as e:
            db.rollback()
            log_audit_event(user_id, user_role, "RITM_SYNC_DB_ERROR", "SNOW_RITMS", latest_blob.name,
                            f"Database error during upsert: {str(e)}")
            return  # Stop execution so we don't archive a failed file
        finally:
            db.close()

        # 5. Archive the file
        archive_blob_name = f"{ARCHIVE_FOLDER}/{latest_blob.name}"
        bucket.copy_blob(latest_blob, bucket, archive_blob_name)
        latest_blob.delete()

    except Exception as e:
        log_audit_event(user_id, user_role, "RITM_SYNC_CRASH", "SNOW_RITMS", "N/A",
                        f"Critical crash in background task: {str(e)}")


def get_last_ritm_sync_date():
    client = get_bq_client()
    if not client:
        return {"last_sync": None}

    query = f"""
        SELECT timestamp 
        FROM `{TABLE_REF}` 
        WHERE action = 'RITM_SYNC_SUCCESS' 
        ORDER BY timestamp DESC 
        LIMIT 1
    """
    try:
        results = list(client.query(query).result())
        if results and results[0].timestamp:
            return {"last_sync": results[0].timestamp.isoformat()}
        return {"last_sync": None}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch last sync from BigQuery: {str(e)}")