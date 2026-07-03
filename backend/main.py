from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import traceback
import os
import time
from jose import jwt
from routers import auth, services, users, regions, countries, assets, tests, board, logs, locations
from routers.auth import require_admin
from database import get_db_connection, release_db_connection
from websockets_manager import manager
from audit_logger import log_audit_event

app = FastAPI(
    title="Isha Core API",
    description="Backend engine for pentest planning and asset management.",
    version="1.0.0"
)

# CORS configuration for local React development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Global Error Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    path = request.url.path
    error_msg = str(exc)

    log_audit_event(
        user_id="SYSTEM",
        username="system@server",
        action="SYSTEM_ERROR",
        resource_type="BACKEND",
        details=f"CRASH at {path}: {error_msg}"
    )

    print("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    return JSONResponse(
        status_code=500,
        content={"detail": "An internal server error occurred. Check the backend logs."}
    )

# Register the routes
app.include_router(auth.router)
app.include_router(services.router)
app.include_router(users.router)
app.include_router(locations.router)
app.include_router(regions.router)
app.include_router(countries.router)
app.include_router(assets.router)
app.include_router(tests.router)
app.include_router(board.router)
app.include_router(logs.router)


# --- WEBSOCKET FOR REACTIVE UI ---
@app.websocket("/ws/board")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()

    # Read the JWT from the secure cookie we set during GitHub login
    token = websocket.cookies.get("access_token")

    if not token:
        await websocket.close(code=1008, reason="Not authenticated")
        return

    try:
        SECRET_KEY = os.getenv("SECRET_KEY", "fallback_secret_key_for_dev")
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        email = payload.get("sub")
        if email is None:
            raise ValueError("Invalid token")
    except Exception as e:
        await websocket.close(code=1008, reason=f"Unauthorized: {str(e)}")
        return

    # Connect the verified user to the board manager
    await manager.connect(websocket, email)

    try:
        while True:
            # We keep the connection open waiting for ping/pong or client messages
            await websocket.receive_text()
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


@app.get("/api/system/ping")
def ping_database(current_user: dict = Depends(require_admin)):
    """Measures actual round-trip latency to the PostgreSQL database."""
    start_time = time.time()
    conn = get_db_connection()
    if not conn:
        return {"status": "offline", "latency_ms": 0}
    try:
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.fetchone()
        cur.close()
    except Exception:
        return {"status": "error", "latency_ms": 0}
    finally:
        release_db_connection(conn)

    latency = round((time.time() - start_time) * 1000, 2)
    return {"status": "online", "latency_ms": latency}


@app.get("/api/health")
def health_check():
    return {"status": "online", "system": "Isha"}
