from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
import os
from routers.auth import require_admin

router = APIRouter(prefix="/api/system/logs", tags=["System Logs"])
LOGS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs")


@router.get("/")
def list_audit_logs(current_user: dict = Depends(require_admin)):
    """Returns a list of all daily log files available for download."""
    if not os.path.exists(LOGS_DIR):
        return {"files": []}

    files = [f for f in os.listdir(LOGS_DIR) if f.endswith(".txt")]
    files.sort(reverse=True)  # Newest files first

    return {"files": files}


@router.get("/{filename}")
def download_audit_log(filename: str, current_user: dict = Depends(require_admin)):
    """Downloads a specific daily log file."""
    # Security check to prevent directory traversal attacks
    if not filename.endswith(".txt") or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid filename.")

    file_path = os.path.join(LOGS_DIR, filename)

    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Log file not found.")

    return FileResponse(path=file_path, filename=filename, media_type="text/plain")