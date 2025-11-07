import os
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response

from .database import init_db, run_startup_migrations, session_context
from .routers import reservations, menu_items, zenchef

load_dotenv()

app = FastAPI(title="FicheCuisineManager")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(menu_items.router)
app.include_router(reservations.router)
app.include_router(zenchef.router)

# Ensure DB
init_db()
# Apply idempotent startup migrations automatically on Railway (PostgreSQL)
try:
    run_startup_migrations()
except Exception as e:
    print(f"Startup migrations skipped due to error: {e}")

# Static serving for built frontend if available
backend_dir = Path(__file__).parent
frontend_dist = (backend_dir / "../frontend/dist").resolve()
assets_dir = (backend_dir / "assets").resolve()
if assets_dir.exists():
    app.mount("/backend-assets", StaticFiles(directory=str(assets_dir)), name="assets")
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dist), html=True), name="static")


# --- Correlation & Request logging middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    try:
        response = await call_next(request)
        duration_ms = int((time.time() - start) * 1000)
        # Add correlation header
        try:
            response.headers["X-Request-ID"] = req_id
        except Exception:
            pass
        # Basic structured log with correlation id
        print(f"REQ {req_id} {request.method} {request.url.path} -> {response.status_code} ({duration_ms}ms)")
        return response
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        print(f"REQ {req_id} {request.method} {request.url.path} -> 500 ({duration_ms}ms) EXC: {e}")
        raise


# --- Exception handlers ---
@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    print(f"HTTPException {exc.status_code} at {request.url.path}: {exc.detail}")
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception):
    print(f"Unhandled exception at {request.url.path}: {exc}")
    return JSONResponse(status_code=500, content={"detail": "Une erreur inattendue est survenue. Veuillez réessayer."})


# --- Favicon (avoid 404 noise) ---
@app.get("/favicon.ico")
async def favicon():
    # If frontend build has a favicon, StaticFiles will serve it; otherwise return 204
    return Response(status_code=204)


# --- Healthcheck ---
@app.get("/health")
async def health():
    ok_db = False
    try:
        with session_context() as s:
            s.exec("SELECT 1")
            ok_db = True
    except Exception:
        ok_db = False
    return {"status": "ok", "db": ok_db}
