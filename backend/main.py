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
import textwrap
from jose import jwt
from routers import (
    auth, services, users, regions, countries, assets, tests, board, logs, locations, insights, contacts, luigi,
    kiss24, danger, documents, rag, kpi_criteria, cronos
)
from routers.auth import require_admin, get_google_public_keys, get_current_user
from database import get_db_connection, run_alembic_migrations
from websockets_manager import manager
from audit_logger import log_audit_event, init_audit_log_infrastructure

init_audit_log_infrastructure()

# --- LIFESPAN MANAGER (Runs on Cloud Run Boot) ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 1. Run Alembic migrations automatically on startup
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

    yield


app = FastAPI(
    title="Isha Core API",
    description=textwrap.dedent("""Isha Backend engine. - [Switch to ReDoc UI](/api-external/redoc)"""),
    version="2.1",
    swagger_ui_parameters={"defaultModelsExpandDepth": -1},
    lifespan=lifespan,
    # Swagger & OpenAPI schema now reside strictly under /api-external
    docs_url="/api-external/docs",
    openapi_url="/api-external/openapi.json",
    redoc_url="/api-external/redoc"
)

env_origins = os.environ.get("ALLOWED_ORIGINS")

if env_origins:
    ALLOWED_ORIGINS = [origin.strip() for origin in env_origins.split(",")]
elif os.environ.get("ENV") == "local":
    ALLOWED_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
else:
    ALLOWED_ORIGINS = []

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def audit_api_usage_middleware(request: Request, call_next):
    start_time = time.time()

    response = await call_next(request)

    user = getattr(request.state, "user", None)

    if user and user.get("auth_method") == "API_KEY":
        path = request.url.path
        user_email = user.get("email", "UNKNOWN_KEY_OWNER")
        role = user.get("role", "UNKNOWN_ROLE")
        duration_ms = round((time.time() - start_time) * 1000, 2)

        # Extract real client IP from Google Load Balancer header
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            # The client IP is the first entry in a comma-separated list
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "UNKNOWN"

        log_audit_event(
            user_id=user_email,
            role=role,
            action=f"API_KEY_{request.method}",
            resource_type="EXTERNAL_API",
            resource_id=path,
            details=f"Endpoint: {path} | Status: {response.status_code} | Latency: {duration_ms}ms | Client IP: {client_ip} | Infrastructure IP: {request.client.host}"
        )

    return response


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

# --- REGISTER ROUTERS ---
# Helper list to cleanly loop and mount standard vs external routes
routers_list = [
    assets.router, kpi_criteria.router, auth.router, board.router,
    contacts.router, countries.router, documents.router, cronos.router, insights.router,
    kiss24.router, locations.router, logs.router, luigi.router,
    rag.router, regions.router, services.router, tests.router,
    users.router, danger.router
]

for r in routers_list:
    # Standard UI Routes (Hidden in Swagger, Protected by IAP)
    app.include_router(r, include_in_schema=False)
    # External API Routes (Visible from Swagger, Bypasses IAP via /api-external prefix)
    app.include_router(r, prefix="/api-external")


# --- WEBSOCKET FOR REACTIVE UI ---
async def handle_websocket_logic(websocket: WebSocket):
    origin = websocket.headers.get("origin")
    if origin not in ALLOWED_ORIGINS and os.environ.get("ENV") != "local":
        await websocket.close(code=1008, reason="Cross-Site Request Blocked")
        return

    await websocket.accept()

    iap_jwt = websocket.headers.get("x-goog-iap-jwt-assertion")
    if not iap_jwt:
        if os.environ.get("ENV") == "local":
            email = os.environ.get("MASTER_ADMIN_EMAIL")
        else:
            await websocket.close(code=1008, reason="Not authenticated via Google IAP")
            return
    else:
        try:
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

    await manager.connect(websocket, email)
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                if payload.get("action") == "ping":
                    continue
            except Exception:
                pass
    except WebSocketDisconnect:
        await manager.disconnect(websocket)


@app.websocket("/ws/board")
async def websocket_endpoint_legacy(websocket: WebSocket):
    await handle_websocket_logic(websocket)


@app.websocket("/api/ws/board")
async def websocket_endpoint_api(websocket: WebSocket):
    await handle_websocket_logic(websocket)


# --- SYSTEM ENDPOINTS ---
@app.get("/api/system/ping", include_in_schema=False)
def ping_database(current_user: dict = Depends(require_admin)):
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
        conn.close()

    latency = round((time.time() - start_time) * 1000, 2)
    return {"status": "online", "latency_ms": latency}


@app.get("/api/health", include_in_schema=False)
def health_check():
    return {"status": "online", "system": "Mario"}


@app.get("/api-external/health", tags=["Health Check"])
def check_health(current_user: dict = Depends(get_current_user)):
    return {"status": "online", "system": "Mario"}

# --- EXCEPTION HANDLER ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    if exc.status_code >= 400:
        # Extract real client IP from Google Load Balancer header
        x_forwarded_for = request.headers.get("X-Forwarded-For")
        if x_forwarded_for:
            client_ip = x_forwarded_for.split(",")[0].strip()
        else:
            client_ip = request.client.host if request.client else "UNKNOWN"

        log_audit_event(
            user_id="UNAUTHENTICATED",
            role="auto_logger",
            action=f"HTTP_{exc.status_code}",
            resource_type="API_SECURITY_ALERT" if exc.status_code in [401, 403] else "API_ERROR",
            resource_id=request.url.path,
            details=f"Method: {request.method} | IP: {client_ip} | Path: {request.url.path} | Error: {str(exc.detail)} | Infrastructure IP: {request.client.host}"
        )
    return JSONResponse({"detail": exc.detail}, status_code=exc.status_code)


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