import os
import requests
import concurrent.futures
import re
import pandas as pd
import uuid
from datetime import datetime, timedelta
import urllib3
import logging
from fastapi import HTTPException
from sqlalchemy.orm import Session
from database import SessionLocal
from models.snitcher import SnitcherMetric
from utils import secret_manager
from audit_logger import log_audit_event

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_PREFIX_MAP = {
    'andre.marques@randstad.com': 'am',
    'iuri.picolini.moro@randstad.com': 'ipm',
    'rodrigo.magalhaes@randstad.com': 'rm',
    'timothy.tjen.a.looi@randstad.com': 'ttal',
    'vito.bonetti@randstadgroep.nl': 'vb',
    'francesco.elisa@randstad.com': 'fe',
    'emin.tosun@randstad.com': 'et',
    'goncalo.antunes@randstad.com': 'ga',
    'hugo.pinto@randstad.com': 'hp'
}


def fetch_page(url, headers):
    response = requests.post(url, headers=headers, verify=False)
    response.raise_for_status()
    return response.json()


def get_all_vulnerabilities(base_url, headers=None, max_threads=20):
    if headers is None: headers = {}
    all_items = []
    endpoint = "vulnerabilities"
    first_page_url = f"{base_url}{endpoint}"

    try:
        first_page = fetch_page(first_page_url, headers)
    except Exception as e:
        logging.error(f"Error fetching first page: {e}")
        return []

    all_items.extend(first_page.get("items", []))
    last_link = first_page.get("_links", {}).get("last")
    total_pages = 1
    if last_link:
        match = re.search(r'page=(\d+)', last_link)
        if match: total_pages = int(match.group(1))

    page_urls = [f"{base_url}{endpoint}?page={i}" for i in range(2, total_pages + 1)]

    with concurrent.futures.ThreadPoolExecutor(max_threads) as executor:
        futures = {executor.submit(fetch_page, url, headers): url for url in page_urls}
        for future in concurrent.futures.as_completed(futures):
            try:
                data = future.result()
                all_items.extend(data.get("items", []))
            except Exception as exc:
                logging.error(f'Generated an exception: {exc}')

    return all_items


def fetch_history(base_url, uuid, headers):
    url = f"{base_url}vulnerabilities/{uuid}/history"
    response = requests.post(url, headers=headers, verify=False)
    response.raise_for_status()
    return {uuid: response.json().get("items", [])}


def get_all_histories(base_url, vulnerabilities, headers=None, max_threads=20):
    if headers is None: headers = {}
    all_histories = {}
    uuids = []
    date_scope = datetime.strptime("2025-01-01", '%Y-%m-%d')

    for vuln in vulnerabilities:
        if "organisation" in vuln and vuln["organisation"]["name"] in ["Integrity", "TMPNL"]:
            continue
        if vuln.get("closed_at") is None or pd.to_datetime(vuln["closed_at"]).replace(tzinfo=None) >= date_scope:
            uuids.append(vuln["uuid"])

    with concurrent.futures.ThreadPoolExecutor(max_threads) as executor:
        futures = {executor.submit(fetch_history, base_url, uuid, headers): uuid for uuid in uuids}
        for future in concurrent.futures.as_completed(futures):
            try:
                all_histories.update(future.result())
            except Exception as exc:
                logging.error(f'Generated an exception fetching history: {exc}')

    return all_histories


def analyze_ticket_metrics(df, start_date, end_date):
    iso_year, week_num, _ = start_date.isocalendar()
    period = f"{iso_year} Week {week_num}"

    before_df = df[df['CREATED_AT'] < start_date]

    metrics = {
        'period': period, 'newly_added_tickets': 0, 'waiting_to_retest_start': 0,
        'waiting_to_retest_end': 0, 'unable_to_retest_start': 0, 'unable_to_retest_end': 0,
        'moved_to_validating': 0, 'moved_to_parked': 0, 'moved_from_parked': 0,
        'moved_unable_to_waiting': 0, 'new_or_open_start': 0, 'new_or_open_end': 0,
        'parked_start': 0, 'parked_end': 0, 'user_metrics': {}
    }

    all_tickets = df['VULN_UUID'].unique()

    # Track new tickets
    for ticket in all_tickets:
        ticket_history = df[df['VULN_UUID'] == ticket].sort_values('CREATED_AT')
        for i in range(1, len(ticket_history)):
            current = ticket_history.iloc[i]
            previous = ticket_history.iloc[i - 1]
            if (start_date <= current['CREATED_AT'] <= end_date and
                    previous['STATE'] == 'Unpublished' and current['STATE'] == 'New'):
                metrics['newly_added_tickets'] += 1
                break

    # Start states
    for ticket in all_tickets:
        ticket_history_before = before_df[before_df['VULN_UUID'] == ticket].sort_values('CREATED_AT')
        if not ticket_history_before.empty:
            latest_state = ticket_history_before.iloc[-1]
            if latest_state['STATE'] == 'Validating' and latest_state['SUB_STATE'] == 'Waiting to Retest':
                metrics['waiting_to_retest_start'] += 1
            if latest_state['STATE'] == 'Validating' and latest_state['SUB_STATE'] == 'Unable to Retest':
                metrics['unable_to_retest_start'] += 1
            if latest_state['STATE'] in ['New', 'Open']:
                metrics['new_or_open_start'] += 1
            if latest_state['STATE'] == 'Parked':
                metrics['parked_start'] += 1

    # End states
    all_history_to_end = df[df['CREATED_AT'] <= end_date]
    for ticket in all_tickets:
        ticket_history_to_end = all_history_to_end[all_history_to_end['VULN_UUID'] == ticket].sort_values('CREATED_AT')
        if not ticket_history_to_end.empty:
            latest_state = ticket_history_to_end.iloc[-1]
            if latest_state['STATE'] == 'Validating' and latest_state['SUB_STATE'] == 'Waiting to Retest':
                metrics['waiting_to_retest_end'] += 1
            if latest_state['STATE'] == 'Validating' and latest_state['SUB_STATE'] == 'Unable to Retest':
                metrics['unable_to_retest_end'] += 1
            if latest_state['STATE'] in ['New', 'Open']:
                metrics['new_or_open_end'] += 1
            if latest_state['STATE'] == 'Parked':
                metrics['parked_end'] += 1

    # Movement and User Metrics
    for ticket in all_tickets:
        ticket_history = df[df['VULN_UUID'] == ticket].sort_values('CREATED_AT')
        for i in range(1, len(ticket_history)):
            current = ticket_history.iloc[i]
            previous = ticket_history.iloc[i - 1]

            if start_date <= current['CREATED_AT'] <= end_date:
                if previous['STATE'] == 'Open' and current['STATE'] == 'Validating':
                    metrics['moved_to_validating'] += 1
                if previous['STATE'] == 'Open' and current['STATE'] == 'Parked':
                    metrics['moved_to_parked'] += 1
                if previous['STATE'] == 'Parked' and current['STATE'] == 'Open':
                    metrics['moved_from_parked'] += 1
                if (previous['STATE'] == 'Validating' and previous['SUB_STATE'] == 'Unable to Retest' and
                        current['STATE'] == 'Validating' and current['SUB_STATE'] == 'Waiting to Retest'):
                    metrics['moved_unable_to_waiting'] += 1

                user = current['CREATED_BY']
                if user not in metrics['user_metrics']:
                    metrics['user_metrics'][user] = {'retesting_to_unable': 0, 'retesting_to_closed': 0,
                                                     'retesting_to_open': 0}

                if previous['STATE'] == 'Validating' and previous['SUB_STATE'] == 'Retesting':
                    if current['STATE'] == 'Validating' and current['SUB_STATE'] == 'Unable to Retest':
                        metrics['user_metrics'][user]['retesting_to_unable'] += 1
                    if current['STATE'] == 'Closed':
                        metrics['user_metrics'][user]['retesting_to_closed'] += 1
                    if current['STATE'] == 'Open':
                        metrics['user_metrics'][user]['retesting_to_open'] += 1

    return metrics


# endpoints
def run_snitcher_sync(user_id: str, user_role: str):
    """Background worker entry point."""
    db = SessionLocal()

    # get previous week number
    current_date = datetime.now()
    previous_date = current_date - timedelta(weeks=1)
    prev_week_number = previous_date.isocalendar()[1]


    try:
        log_audit_event(
            user_id=str(user_id),
            role=user_role,
            action="SNITCHER_SYNC_START",
            resource_type="SNITCHER",
            resource_id=f"Week {prev_week_number}",
            details=f"Snitcher sync started in the background. Check logs for completion."
        )

        # Pull API key securely (Replace with your vault method if needed)
        api_key = secret_manager.get_secret(os.environ.get("KISS_24_API_KEY_NAME"))
        if not api_key:
            log_audit_event(
                user_id=str(user_id),
                role=user_role,
                action="NO_KIIS_24_API_KEY",
                resource_type="SNITCHER",
                resource_id=f"API key",
                details=f"KISS_24_API_KEY_NAME environment variable is missing."
            )
            return

        base_url = os.environ.get("KISS_24_ENDPOINT")
        headers = {"X-Api-Key": api_key, "Content-Type": "application/json"}

        vulnerabilities = get_all_vulnerabilities(base_url, headers=headers)
        if not vulnerabilities:
            log_audit_event(
                user_id=str(user_id),
                role=user_role,
                action="SNITCHER_NO_VULN",
                resource_type="SNITCHER",
                resource_id=f"Week {prev_week_number}",
                details=f"No vulnerabilities retrieved. Exiting sync."
            )
            return

        devo_count = [0, 0]
        for vuln in vulnerabilities:
            if "organisation" in vuln and vuln["organisation"]["name"] in ["Integrity", "TMPNL"]:
                continue
            email = vuln.get("created_by", {}).get("email", "").lower()
            if "devoteam" in email:
                if vuln.get("sub_state") == "Waiting to Retest": devo_count[0] += 1
                if vuln.get("sub_state") == "Unable to Retest": devo_count[1] += 1

        histories = get_all_histories(base_url, vulnerabilities, headers=headers)

        # Convert to in-memory Pandas DataFrame instead of CSV
        history_records = []
        for key, values in histories.items():
            for value in values:
                history_records.append({
                    "VULN_UUID": key,
                    "CREATED_AT": value.get("created_at"),
                    "STATE": value.get("state"),
                    "SUB_STATE": value.get("sub_state"),
                    "CREATED_BY": value.get("created_by", {}).get("email", "unknown")
                })

        df = pd.DataFrame(history_records)
        df['CREATED_AT'] = pd.to_datetime(df['CREATED_AT']).dt.tz_localize(None)

        # Calculate Dates
        today = datetime.now()
        last_week_day = today - timedelta(days=7)
        start_of_last_week = last_week_day - timedelta(days=last_week_day.weekday())
        end_of_last_week = start_of_last_week + timedelta(days=6)

        start_date = start_of_last_week.replace(hour=0, minute=0, second=0)
        end_date = end_of_last_week.replace(hour=23, minute=59, second=59)

        metrics = analyze_ticket_metrics(df, start_date, end_date)

        # Insert into Postgres
        db_record = SnitcherMetric(
            id=uuid.uuid4(),
            period=metrics['period'],
            newly_added=metrics['newly_added_tickets'],
            start_new_open=metrics['new_or_open_start'],
            start_waiting_to_retest=metrics['waiting_to_retest_start'],
            start_unable_to_retest=metrics['unable_to_retest_start'],
            start_parked=metrics['parked_start'],
            end_new_open=metrics['new_or_open_end'],
            end_waiting_to_retest=metrics['waiting_to_retest_end'],
            end_unable_to_retest=metrics['unable_to_retest_end'],
            end_parked=metrics['parked_end'],
            solved=metrics['moved_to_validating'],
            parked=metrics['moved_to_parked'],
            unparked=metrics['moved_from_parked'],
            unable_to_waiting=metrics['moved_unable_to_waiting'],
            devoteam_waiting_to_retest=devo_count[0],
            devoteam_unable_to_retest=devo_count[1]
        )

        # Initialize the totals
        total_utr = 0
        total_nf = 0
        total_c = 0

        for email, prefix in USER_PREFIX_MAP.items():
            user_data = metrics['user_metrics'].get(email, {'retesting_to_unable': 0, 'retesting_to_open': 0,
                                                            'retesting_to_closed': 0})
            setattr(db_record, f"{prefix}_utr", user_data['retesting_to_unable'])
            setattr(db_record, f"{prefix}_nf", user_data['retesting_to_open'])
            setattr(db_record, f"{prefix}_c", user_data['retesting_to_closed'])

            # Increment totals
            total_utr += user_data['retesting_to_unable']
            total_nf += user_data['retesting_to_open']
            total_c += user_data['retesting_to_closed']

        db_record.total_unable_to_retest = total_utr
        db_record.total_not_fixed_reopened = total_nf
        db_record.total_closed = total_c

        db.add(db_record)
        db.commit()

        log_audit_event(
            user_id=str(user_id),
            role=user_role,
            action="SNITCHER_SYNC_SUCCESS",
            resource_type="SNITCHER",
            resource_id=f"Week {prev_week_number}",
            details=f"Successfully inserted Snitcher metrics for {prev_week_number}"
        )

    except Exception as e:
        db.rollback()
        log_audit_event(
            user_id=str(user_id),
            role=user_role,
            action="SNITCHER_SYNC_FAIL",
            resource_type="SNITCHER",
            resource_id=f"Week {prev_week_number}",
            details=f"Snitcher metrics for {prev_week_number} FAILED: {e}"
        )
    finally:
        db.close()


def get_all_metrics(db: Session):
    """Fetches all historical metrics, ordered by the most recent period first."""
    return db.query(SnitcherMetric).order_by(SnitcherMetric.period.desc()).all()


def wipe_all_metrics(db: Session):
    """Truncates the Snitcher metrics table."""
    try:
        deleted_count = db.query(SnitcherMetric).delete()
        db.commit()
        return {"message": f"Successfully deleted {deleted_count} Snitcher metric records."}
    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to wipe metrics: {str(e)}")