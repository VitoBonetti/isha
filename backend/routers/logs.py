from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import FileResponse
import os
from pathlib import Path
from routers.auth import require_admin
from audit_logger import log_audit_event

router = APIRouter(prefix="/api/system/logs", tags=["System Logs"])
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


def get_safe_log_path(filename: str) -> Path:
    # reject dangerous characters immediately
    if "\0" in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid filename format.")
    # force basename extraction as a secondary safeguard
    safe_name = os.path.basename(filename)
    if not safe_name.endswith(".txt"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid file extension. Only .txt allowed.")
    # resolve absolute paths
    base_dir = Path(LOGS_DIR).resolve()
    file_path = (base_dir / safe_name).resolve()
    # final strict boundary check
    if not str(file_path).startswith(str(base_dir)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Path traversal blocked.")

    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Log file not found.")

    return file_path


@router.get("/", summary="[Admin Only]")
def list_audit_logs(current_user: dict = Depends(require_admin)):
    """Returns a list of all daily log files available for download."""
    if not os.path.exists(LOGS_DIR):
        return {"files": []}

    files = [f for f in os.listdir(LOGS_DIR) if f.endswith(".txt")]
    files.sort(reverse=True)

    return {"files": files}


@router.get("/{filename}", summary="[Admin Only]")
def download_audit_log(filename: str, current_user: dict = Depends(require_admin)):
    """Downloads a specific daily log file."""
    file_path = get_safe_log_path(filename)

    log_audit_event(
        user_id=str(current_user["id"]),
        role=current_user["role"],
        action="LOGS_DOWNLOADED",
        resource_type="LOGS",
        resource_id="N/A",
        details=f"Logs {filename} downloaded."
    )

    return FileResponse(path=str(file_path), filename=filename, media_type="text/plain")


@router.delete("/{filename}", summary="[Admin Only]")
def delete_audit_log(filename: str, current_user: dict = Depends(require_admin)):
    """Deletes a specific daily log file."""
    file_path = get_safe_log_path(filename)
    try:
        os.remove(file_path)

        log_audit_event(
            user_id=str(current_user["id"]),
            role=current_user["role"],
            action="LOGS_DELETED",
            resource_type="LOGS",
            resource_id="N/A",
            details=f"Logs {filename} deleted."
        )

        return {"message": "Log file deleted."}
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Failed to delete file.")