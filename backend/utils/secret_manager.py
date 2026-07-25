from __future__ import annotations
from typing import Any
from google.cloud import secretmanager
import os
from audit_logger import log_audit_event


def get_secret(secret_id: str) -> Any | None:
    """
    Dynamically fetches the latest version of a secret from GCP Secret Manager.
    Returns the raw string value.
    """
    project_id = os.environ.get("GCP_PROJECT_ID")
    if not project_id:
        raise EnvironmentError("GCP_PROJECT_ID environment variable is missing.")

    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{project_id}/secrets/{secret_id}/versions/latest"

    try:
        response = client.access_secret_version(request={"name": name})
        return response.payload.data.decode("UTF-8")
    except Exception as e:
        print(f"Failed to retrieve secret '{secret_id}': {e}")
        return None