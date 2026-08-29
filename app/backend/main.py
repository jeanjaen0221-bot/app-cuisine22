import os
import re
import time
import uuid
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import JSONResponse, Response, FileResponse, StreamingResponse

from .database import init_db, run_startup_migrations, session_context, backfill_allergen_icons
from .gpt_api import gpt_app
from .models import User
from .security import decode_access_token
from .routers import auth, reservations, menu_items, zenchef, allergens, notes, drinks, suppliers, purchase_orders, floorplan, incidents, facturation, reminders

load_dotenv()

app = FastAPI(title="FicheCuisineManager")

# CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Ordered access rules: (path pattern, permissions that grant it, methods it
# covers). The first rule whose pattern and method both match wins, so the more
# specific entries come first. A path matching no rule is refused for members —
# a new route defaults to closed rather than open.
#
# Facturation is not a URL prefix of its own: its endpoints live under
# /api/supplement-presets and /api/reservations/{id}/{billing,supplements}. They
# must be listed explicitly, otherwise the "billing" permission grants nothing.
API_PERMISSION_RULES: tuple[tuple[re.Pattern[str], tuple[str, ...], tuple[str, ...] | None], ...] = tuple(
    (re.compile(pattern), permissions, methods)
    for pattern, permissions, methods in (
        (r"^/api/reservations/rooftop", ("rooftop",), None),
        (r"^/api/reservations/[^/]+/(billing|supplements|invoice-pdf)", ("billing", "reservations"), None),
        # The billing panel is embedded in the fiche screen too, so it must be
        # readable there; only Facturation edits the preset library itself.
        (r"^/api/supplement-presets", ("billing", "reservations"), ("GET", "HEAD")),
        (r"^/api/supplement-presets", ("billing",), None),
        # Facturation lists reservations to choose which one to invoice, read-only.
        (r"^/api/reservations", ("reservations", "billing"), ("GET", "HEAD")),
        (r"^/api/reservations", ("reservations",), None),
        (r"^/api/reminders", ("reservations",), None),
        (r"^/api/floorplan", ("floorplan",), None),
        (r"^/api/menu-items", ("menu",), None),
        (r"^/api/drinks", ("orders",), None),
        (r"^/api/purchase-orders", ("orders",), None),
        (r"^/api/suppliers", ("suppliers",), None),
        (r"^/api/incidents", ("incidents",), None),
        (r"^/api/zenchef", ("settings",), None),
        (r"^/api/allergens", ("settings",), None),
        (r"^/api/notes", ("dashboard",), None),
    )
)


def permissions_required_for(path: str, method: str) -> tuple[str, ...] | None:
    """Permissions that grant `method path`, or None when no rule covers it."""
    for pattern, permissions, methods in API_PERMISSION_RULES:
        if pattern.match(path) and (methods is None or method.upper() in methods):
            return permissions
    return None


@app.middleware("http")
async def require_api_authentication(request: Request, call_next):
    """Protect every business API route; authentication endpoints stay public."""
    path = request.url.path
    # /api/auth/* is handled by the router itself (public setup/login, and
    # require_admin on the user-management routes). /api/gpt/* is a separate
    # sub-app (gpt_api.py) with its own API-key auth, not the human JWT login.
    if path.startswith("/api/") and not path.startswith("/api/auth/") and not path.startswith("/api/gpt/"):
        scheme, _, token = request.headers.get("Authorization", "").partition(" ")
        if scheme.lower() != "bearer" or not token:
            return JSONResponse(status_code=401, content={"detail": "Authentification requise."})
        try:
            request.state.user_id = decode_access_token(token)
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
        with session_context() as session:
            user = session.get(User, uuid.UUID(request.state.user_id))
            if user is None:
                return JSONResponse(status_code=401, content={"detail": "Session invalide ou expirée."})
            accepted = permissions_required_for(path, request.method)
            permissions = {item for item in (user.permissions or "").split(",") if item}
            # Accounts created before roles existed are the original owner
            # account; keep its access even if a legacy migration returned NULL.
            if (user.role or "admin") != "admin" and (accepted is None or permissions.isdisjoint(accepted)):
                return JSONResponse(status_code=403, content={"detail": "Vous n’avez pas accès à cette section."})
    return await call_next(request)

# Routers
app.include_router(auth.router)
app.include_router(menu_items.router)
app.include_router(reservations.router)
app.include_router(zenchef.router)
app.include_router(allergens.router)
app.include_router(notes.router)
app.include_router(drinks.router)
app.include_router(suppliers.router)
app.include_router(purchase_orders.router)
app.include_router(floorplan.router)
app.include_router(incidents.router)
app.include_router(facturation.router)
app.include_router(reminders.router)

# Dedicated, API-key-authenticated surface for a Custom GPT Action (see gpt_api.py).
# Mounted before the static/SPA fallback below so /api/gpt/* is never swallowed by it.
app.mount("/api/gpt", gpt_app)

# Ensure DB
init_db()
# Backfill existing allergen icons into DB rows (idempotent)
try:
    backfill_allergen_icons()
except Exception as e:
    print(f"Backfill allergen icons skipped: {e}")
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
    assets_subdir = (frontend_dist / "assets")
    if assets_subdir.exists():
        app.mount("/assets", StaticFiles(directory=str(assets_subdir)), name="frontend-assets")


# --- Correlation & Request logging middleware ---
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    request.state.request_id = req_id
    is_salle = request.url.path.startswith("/api/floorplan")
    salle_debug = request.headers.get("X-Salle-Debug") == "1"
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
        # Salle-specific HTTP log line for Railway
        if is_salle:
            ua = request.headers.get("user-agent", "-")
            ip = (request.client.host if request.client else "-")
            q = ("?" + request.url.query) if request.url.query else ""
            clen = response.headers.get("content-length", "-")
            print(
                f"SALLE HTTP | id={req_id} | {request.method} {request.url.path}{q} -> {response.status_code} ({duration_ms}ms) | ip={ip} | ua={ua} | len={clen}"
            )
        if is_salle and salle_debug:
            try:
                from .routers.floorplan import _dbg_buffer
                # dump last ~50 buffer lines to stdout for quick tailing
                tail = list(_dbg_buffer)[-50:]
                print("SALLE DEBUG DUMP START")
                for item in tail:
                    print(f"{item['ts']} {item['lvl']} {item['msg']}")
                print("SALLE DEBUG DUMP END")
            except Exception:
                pass
        return response
    except Exception as e:
        duration_ms = int((time.time() - start) * 1000)
        print(f"REQ {req_id} {request.method} {request.url.path} -> 500 ({duration_ms}ms) EXC: {e}")
        if is_salle:
            ua = request.headers.get("user-agent", "-")
            ip = (request.client.host if request.client else "-")
            q = ("?" + request.url.query) if request.url.query else ""
            print(
                f"SALLE HTTP | id={req_id} | {request.method} {request.url.path}{q} -> 500 ({duration_ms}ms) | ip={ip} | ua={ua} | err={e}"
            )
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
        from sqlalchemy import text
        with session_context() as s:
            s.exec(text("SELECT 1"))
            ok_db = True
    except Exception:
        ok_db = False
    return {"status": "ok", "db": ok_db}


@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    index_file = frontend_dist / "index.html"
    if not index_file.exists():
        raise HTTPException(status_code=404, detail="Frontend build not found")
    if (
        full_path.startswith("api")
        or full_path.startswith("backend-assets")
        or full_path.startswith("assets")
        or full_path in {"favicon.ico", "health", "docs", "redoc", "openapi.json"}
    ):
        raise HTTPException(status_code=404)
    return FileResponse(str(index_file))
