from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
import asyncio
import traceback
import os
import time
import json
from jose import jwt, JWTError
from routers import (
    auth, services, users, regions, countries, assets, tests, board, logs, locations, insights, contacts, luigi,
    kiss24, danger, documents, rag, kpi_criteria
)
from routers.rag import start_nightly_rag_scheduler
from routers.auth import require_admin, get_google_public_keys
from database import get_db_connection, run_alembic_migrations
from websockets_manager import manager
from audit_logger import log_audit_event, init_audit_log_infrastructure


init_audit_log_infrastructure()

# --- LIFESPAN MANAGER (Runs on Cloud Run Boot) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Start the nightly 24-hour RAG sync scheduler
    scheduler_task = asyncio.create_task(start_nightly_rag_scheduler())
    print("⏰ Nightly RAG sync scheduler initialized.")

    # 2. Run Alembic migrations automatically on startup
    try:
        print("Starting up and checking database migrations...")
        run_alembic_migrations()
        print("Migrations complete.")
    except Exception as e:
        print("🚨 CRITICAL MIGRATION ERROR:")
        traceback.print_exc()
        raise e

    # 2. Check Database Connection
    conn = get_db_connection()
    if conn:
        print("✅ System normal. Database connected.")
        conn.close()
    else:
        print("🚨 CRITICAL: Cannot reach Cloud SQL via IAM. Check Service Account permissions.")

    yield # The application runs here!


app = FastAPI(
    title="Isha Core API",
    description="Backend engine for pentest planning and asset management.",
    version="1.3.1",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    lifespan=lifespan,
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
    redoc_url="/api/redoc"
)

env_origins = os.environ.get("ALLOWED_ORIGINS")

if env_origins:
    # PRODUCTION
    ALLOWED_ORIGINS = [origin.strip() for origin in env_origins.split(",")]
elif os.environ.get("ENV") == "local":
    # LOCAL DEV
    ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
else:
    # Fail safe
    ALLOWED_ORIGINS = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- GLOBAL ERROR HANDLER ---
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
app.include_router(assets.router)
app.include_router(kpi_criteria.router)
app.include_router(auth.router)
app.include_router(board.router)
app.include_router(contacts.router)
app.include_router(countries.router)
app.include_router(documents.router)
app.include_router(insights.router)
app.include_router(kiss24.router)
app.include_router(locations.router)
app.include_router(logs.router)
app.include_router(luigi.router)
app.include_router(rag.router)
app.include_router(regions.router)
app.include_router(services.router)
app.include_router(tests.router)
app.include_router(users.router)
app.include_router(danger.router)


# --- WEBSOCKET FOR REACTIVE UI ---

# Centralized handler logic
async def handle_websocket_logic(websocket: WebSocket):
    # CSRF Protection
    origin = websocket.headers.get("origin")
    if origin not in ALLOWED_ORIGINS and os.environ.get("ENV") != "local":
        await websocket.close(code=1008, reason="Cross-Site Request Blocked")
        return

    await websocket.accept()

    # Read the secure JWT header attached by Google IAP
    iap_jwt = websocket.headers.get("x-goog-iap-jwt-assertion")
    if not iap_jwt:
        if os.environ.get("ENV") == "local":
            email = os.environ.get("MASTER_ADMIN_EMAIL")
        else:
            await websocket.close(code=1008, reason="Not authenticated via Google IAP")
            return
    else:
        try:
            # Verify the IAP JWT cryptographically
            kid = jwt.get_unverified_header(iap_jwt).get("kid")
            public_keys = get_google_public_keys()
            public_key = public_keys.get(kid)
            if not public_key:
                raise ValueError("Invalid IAP Token Header Key ID")
            payload = jwt.decode(
                iap_jwt,
                public_key,
                algorithms=["ES256"],
                audience=os.environ.get("IAP_AUDIENCE")
            )
            email = payload.get("email")
            if not email:
                raise ValueError("No email found in IAP payload")
        except Exception as e:
            await websocket.close(code=1008, reason=f"Unauthorized: {str(e)}")
            return

    # Connect the verified user to the board manager
    await manager.connect(websocket, email)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("action") == "ping":
                    continue  # Do nothing, just loop back
            except Exception:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


# Route 1
@app.websocket("/ws/board")
async def websocket_endpoint_legacy(websocket: WebSocket):
    await handle_websocket_logic(websocket)


# Route 2 (The one your frontend is actively hitting)
@app.websocket("/api/ws/board")
async def websocket_endpoint_api(websocket: WebSocket):
    await handle_websocket_logic(websocket)


# --- SYSTEM ENDPOINTS ---
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
        # Replaced release_db_connection with conn.close()
        conn.close()

    latency = round((time.time() - start_time) * 1000, 2)
    return {"status": "online", "latency_ms": latency}


@app.get("/api/health")
def health_check():
    return {"status": "online", "system": "Mario"}


#  Automatically log HTTP errors (400, 401, 403, 404, etc.)
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    # We only care about logging client and server errors, not standard redirects
    if exc.status_code >= 400:
        log_audit_event(
            user_id="SYSTEM",
            role="auto_logger",
            action=f"HTTP_{exc.status_code}",
            resource_type="API_ERROR",
            resource_id=request.url.path,
            details=f"Method: {request.method} | Error: {str(exc.detail)}"
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


#  Automatically log full system crashes (500)
@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    log_audit_event(
        user_id="SYSTEM",
        role="auto_logger",
        action="HTTP_500",
        resource_type="SYSTEM_CRASH",
        resource_id=request.url.path,
        details=f"Method: {request.method} | Exception: {str(exc)}"
    )
    return JSONResponse({"detail": "Internal Server Error"}, status_code=500)