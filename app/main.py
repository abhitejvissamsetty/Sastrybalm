from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.observability import (
    configure_observability,
    metrics_response,
    observe_request,
)
from app.services.audit import audit_request

from app.routers import auth, dashboard, geography, positions, beats, outlets, products, users, company, onboarding
from app.routers import orders, payments, expenses, timesheets, tracking, analytics, material_requests
from app.routers import asset_capitalizations, vendors, attendance, approvals, flags, inventory, retailing, procurement
from app.routers import settings as settings_router
from app.routers.api import auth as api_auth
from app.routers.api import master as api_master
from app.routers.api import operations as api_operations
from app.routers.api import leaves as api_leaves
from app.routers.api import journey_plan as api_journey_plan
from app.routers.api import procurement_workflow as api_procurement_workflow
from app.services.startup_validation import (
    readiness_checks,
    validate_admin_and_s3_config,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations are run by entrypoint.sh BEFORE Gunicorn forks workers.
    # Background jobs run in the dedicated scheduler container/process.
    settings.validate_runtime_security()
    try:
        validate_admin_and_s3_config()
    except Exception as e:
        print(f"Lifespan startup validation error: {e}")
    yield



app = FastAPI(
    title=settings.app_name,
    description="Field Sales Force Automation — Admin Dashboard & Mobile API",
    version="1.0.0",
    docs_url="/api/docs" if settings.enable_api_docs else None,
    redoc_url="/api/redoc" if settings.enable_api_docs else None,
    lifespan=lifespan,
)
configure_observability()
app.middleware("http")(observe_request)
app.middleware("http")(audit_request)


@app.get("/health/live", include_in_schema=False)
async def liveness():
    return {"status": "ok"}


@app.get("/health/ready", include_in_schema=False)
async def readiness():
    checks = readiness_checks()
    ready = all(checks.values())
    return JSONResponse(
        {"status": "ready" if ready else "not_ready", "checks": checks},
        status_code=200 if ready else 503,
    )


@app.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    return metrics_response(request)


app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.trusted_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=86400 * 7,
    https_only=settings.secure_cookies,
    same_site="lax",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

from app.database import SessionLocal
from app.services.auth import is_system_onboarded


@app.middleware("http")
async def enforce_onboarding_middleware(request: Request, call_next):
    path = request.url.path
    # Exempt static files, API calls, and the onboarding route itself
    if (
        path.startswith("/static")
        or path.startswith("/onboarding")
        or path.startswith("/api/")
        or path.startswith("/health/")
    ):
        return await call_next(request)

    db = SessionLocal()
    try:
        if not is_system_onboarded(db):
            return RedirectResponse("/onboarding", status_code=302)
    except Exception as e:
        print(f"Onboarding middleware check error: {e}")
        return RedirectResponse("/onboarding", status_code=302)
    finally:
        db.close()

    return await call_next(request)


@app.middleware("http")
async def prevent_browser_caching_middleware(request: Request, call_next):
    response = await call_next(request)
    path = request.url.path
    if not path.startswith("/static"):
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(self), geolocation=(self), microphone=()"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; "
        "base-uri 'self'; frame-ancestors 'none'; object-src 'none'; "
        "img-src 'self' data: blob: https:; "
        "font-src 'self' data: https:; "
        "style-src 'self' 'unsafe-inline' https:; "
        "script-src 'self' 'unsafe-inline'; "
        "connect-src 'self' https:; form-action 'self'"
    )
    if settings.secure_cookies:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response


_templates = Jinja2Templates(directory="app/templates")
from app.utils.timezone import format_ist
_templates.env.filters["format_ist"] = format_ist

from app.routers import backup, channel_partners, warehouses

# Web routers
app.include_router(onboarding.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(geography.router)
app.include_router(positions.router)
app.include_router(beats.router)
app.include_router(retailing.router)
app.include_router(outlets.router)
app.include_router(products.router)
app.include_router(warehouses.router)
app.include_router(channel_partners.router)
app.include_router(inventory.router)
app.include_router(settings_router.router)
app.include_router(backup.router)
app.include_router(users.router)
app.include_router(company.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(expenses.router)
app.include_router(timesheets.router)
app.include_router(tracking.router)
app.include_router(analytics.router)
app.include_router(material_requests.router)
app.include_router(procurement.router)
app.include_router(asset_capitalizations.router)
app.include_router(vendors.router)
app.include_router(attendance.router)
app.include_router(approvals.router)
app.include_router(flags.router)
app.include_router(analytics.action_center_alerts_router)

# Legacy URL compatibility redirects with sub-path wildcard support
@app.api_route("/attendance{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_attendance(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/tracking/attendance{rest}{qs}", status_code=307)

@app.api_route("/orders{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_orders(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/operations/orders{rest}{qs}", status_code=307)

@app.api_route("/expenses{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_expenses(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/operations/expenses{rest}{qs}", status_code=307)

@app.api_route("/timesheets{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_timesheets(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    if rest.startswith("/visits"):
        rest = rest.replace("/visits/all", "").replace("/visits", "")
        return RedirectResponse(f"/tracking/visits{rest}{qs}", status_code=307)
    return RedirectResponse(f"/operations/timesheets{rest}{qs}", status_code=307)

@app.api_route("/material-requests{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_mrs(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/operations/material-requests{rest}{qs}", status_code=307)

@app.api_route("/asset-capitalizations{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_ac(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/operations/marketing-assets{rest}{qs}", status_code=307)

@app.api_route("/approvals{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_approvals(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/action-center/approvals{rest}{qs}", status_code=307)

@app.api_route("/flags{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_flags(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/action-center/flags{rest}{qs}", status_code=307)

@app.api_route("/products{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_products(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/catalogue/products{rest}{qs}", status_code=307)

@app.api_route("/inventory{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_inventory(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/catalogue/inventory{rest}{qs}", status_code=307)

@app.api_route("/warehouses{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_warehouses(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/catalogue/warehouses{rest}{qs}", status_code=307)

@app.api_route("/geography{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_geography(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/master-data/geography{rest}{qs}", status_code=307)

@app.api_route("/users{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_users(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/master-data/users{rest}{qs}", status_code=307)

@app.api_route("/positions{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_positions(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/master-data/positions{rest}{qs}", status_code=307)

@app.api_route("/beats{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_beats(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/master-data/beats{rest}{qs}", status_code=307)

@app.api_route("/outlets{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_outlets(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/master-data/outlets{rest}{qs}", status_code=307)

@app.api_route("/channel-partners{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_cps(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/master-data/channel-partners{rest}{qs}", status_code=307)

@app.api_route("/vendors{rest:path}", methods=["GET", "POST"], include_in_schema=False)
async def legacy_vendors(request: Request, rest: str = ""):
    qs = ("?" + request.url.query) if request.url.query else ""
    return RedirectResponse(f"/master-data/vendors{rest}{qs}", status_code=307)
app.include_router(api_auth.router)
app.include_router(api_master.router)
app.include_router(api_operations.router)
app.include_router(api_leaves.router)
from app.routers import admin_leaves
app.include_router(admin_leaves.router)
app.include_router(api_journey_plan.router)
app.include_router(api_procurement_workflow.router)


@app.exception_handler(401)
async def unauthorized_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        detail = getattr(exc, "detail", "Not authenticated")
        return JSONResponse({"detail": detail}, status_code=401)
    return RedirectResponse("/login", status_code=302)


from app.dependencies import get_current_web_user
from app.database import SessionLocal


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    detail = getattr(exc, "detail", "You don't have permission to view this page. Contact your administrator if you believe this is an error.")
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": detail}, status_code=403)
    db = SessionLocal()
    try:
        user = get_current_web_user(request, db)
    finally:
        db.close()
    return _templates.TemplateResponse(
        request=request,
        name="errors/403.html",
        context={"current_user": user, "detail": detail},
        status_code=403,
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    db = SessionLocal()
    try:
        user = get_current_web_user(request, db)
    finally:
        db.close()
    return _templates.TemplateResponse(
        request=request,
        name="errors/404.html",
        context={"current_user": user},
        status_code=404,
    )
