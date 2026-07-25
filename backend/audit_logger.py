import os
import re
from datetime import datetime

# Automatically create a 'logs' directory inside the backend folder
LOGS_DIR = os.path.join(os.path.dirname(__file__), "logs")
os.makedirs(LOGS_DIR, exist_ok=True)


def sanitize_details(details: str) -> str:
    """Removes sensitive patterns like passwords or tokens from log strings."""
    if not details:
        return details

    patterns = [
        (r'(password["\s:=]+)["\']?([^"\'\s,]+)["\']?', r'\1[REDACTED]'),
        (r'(secret["\s:=]+)["\']?([^"\'\s,]+)["\']?', r'\1[REDACTED]'),
        (r'(token["\s:=]+)["\']?([^"\'\s,]+)["\']?', r'\1[REDACTED]'),
        (r'(eyJ[A-Za-z0-9-_=]+\.[A-Za-z0-9-_=]+\.?[A-Za-z0-9-_.+/=]*)', '[JWT_REDACTED]')
    ]

    sanitized = details
    for pattern, replacement in patterns:
        sanitized = re.sub(pattern, replacement, sanitized, flags=re.IGNORECASE)
    return sanitized


def log_audit_event(user_id: str, role: str, action: str, resource_type: str, resource_id: str = None,
                    details: str = None):
    """Appends an event to the daily log file."""
    today = datetime.now().strftime("%Y-%m-%d")
    log_filename = os.path.join(LOGS_DIR, f"audit_{today}.txt")
    timestamp = datetime.now().isoformat()

    clean_details = sanitize_details(details)

    # Format: [TIMESTAMP] USER_EMAIL | ACTION | RESOURCE | DETAILS
    log_entry = f"[{timestamp}] ROLE:{role} | USER_ID: {user_id} | ACTION:{action} | RESOURCE:{resource_type} | TARGET:{resource_id} | DETAILS:{clean_details}\n"

    try:
        with open(log_filename, "a", encoding="utf-8") as f:
            f.write(log_entry)
    except Exception as e:
        print(f"Failed to write to local audit log: {e}")