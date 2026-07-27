from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

from app.routers import auth, dashboard, geography, positions, beats, outlets, products, users, company, onboarding
from app.routers import orders, payments, expenses, timesheets, tracking, analytics, material_requests
from app.routers import asset_capitalizations, vendors, attendance, approvals, flags, inventory
from app.routers import settings as settings_router
from app.routers.api import auth as api_auth
from app.routers.api import master as api_master
from app.routers.api import operations as api_operations
from app.routers.api import webhooks as api_webhooks
from app.scheduler import start_scheduler, scheduler
from app.services.startup_validation import validate_admin_and_s3_config

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Migrations are run by entrypoint.sh BEFORE Gunicorn forks workers.
    # Workers only need to validate config and start the scheduler.
    try:
        validate_admin_and_s3_config()
    except Exception as e:
        print(f"Lifespan startup validation error: {e}")
    start_scheduler()
    yield
    scheduler.shutdown(wait=False)



app = FastAPI(
    title=settings.app_name,
    description="Field Sales Force Automation — Admin Dashboard & Mobile API",
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex="https?://.*",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(
    SessionMiddleware,
    secret_key=settings.secret_key,
    max_age=86400 * 7,
    https_only=False,
    same_site="lax",
)

app.mount("/static", StaticFiles(directory="app/static"), name="static")

from app.database import SessionLocal
from app.services.auth import is_system_onboarded


@app.middleware("http")
async def enforce_onboarding_middleware(request: Request, call_next):
    path = request.url.path
    # Exempt static files, API calls, and the onboarding route itself
    if path.startswith("/static") or path.startswith("/onboarding") or path.startswith("/api/"):
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


_templates = Jinja2Templates(directory="app/templates")

from app.routers import backup, channel_partners, warehouses

# Web routers
app.include_router(onboarding.router)
app.include_router(auth.router)
app.include_router(dashboard.router)
app.include_router(geography.router)
app.include_router(positions.router)
app.include_router(beats.router)
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
app.include_router(asset_capitalizations.router)
app.include_router(vendors.router)
app.include_router(attendance.router)
app.include_router(approvals.router)
app.include_router(flags.router)
app.include_router(analytics.action_center_alerts_router)

# Legacy URL compatibility redirects
@app.get("/attendance", include_in_schema=False)
async def legacy_attendance(): return RedirectResponse("/tracking/attendance", status_code=307)

@app.get("/orders", include_in_schema=False)
async def legacy_orders(): return RedirectResponse("/operations/orders", status_code=307)

@app.get("/expenses", include_in_schema=False)
async def legacy_expenses(): return RedirectResponse("/operations/expenses", status_code=307)

@app.get("/timesheets", include_in_schema=False)
async def legacy_timesheets(): return RedirectResponse("/operations/timesheets", status_code=307)

@app.get("/material-requests", include_in_schema=False)
async def legacy_mrs(): return RedirectResponse("/operations/material-requests", status_code=307)

@app.get("/asset-capitalizations", include_in_schema=False)
async def legacy_ac(): return RedirectResponse("/operations/marketing-assets", status_code=307)

@app.get("/approvals", include_in_schema=False)
async def legacy_approvals(): return RedirectResponse("/action-center/approvals", status_code=307)

@app.get("/flags", include_in_schema=False)
async def legacy_flags(): return RedirectResponse("/action-center/flags", status_code=307)

@app.get("/products", include_in_schema=False)
async def legacy_products(): return RedirectResponse("/catalogue/products", status_code=307)

@app.get("/inventory", include_in_schema=False)
async def legacy_inventory(): return RedirectResponse("/catalogue/inventory", status_code=307)

@app.get("/warehouses", include_in_schema=False)
async def legacy_warehouses(): return RedirectResponse("/catalogue/warehouses", status_code=307)

@app.get("/geography", include_in_schema=False)
async def legacy_geography(): return RedirectResponse("/master-data/geography", status_code=307)

@app.get("/users", include_in_schema=False)
async def legacy_users(): return RedirectResponse("/master-data/users", status_code=307)

@app.get("/positions", include_in_schema=False)
async def legacy_positions(): return RedirectResponse("/master-data/positions", status_code=307)

@app.get("/beats", include_in_schema=False)
async def legacy_beats(): return RedirectResponse("/master-data/beats", status_code=307)

@app.get("/outlets", include_in_schema=False)
async def legacy_outlets(): return RedirectResponse("/master-data/outlets", status_code=307)

@app.get("/channel-partners", include_in_schema=False)
async def legacy_cps(): return RedirectResponse("/master-data/channel-partners", status_code=307)

@app.get("/vendors", include_in_schema=False)
async def legacy_vendors(): return RedirectResponse("/master-data/vendors", status_code=307)
app.include_router(api_auth.router)
app.include_router(api_master.router)
app.include_router(api_operations.router)
app.include_router(api_webhooks.router)


@app.post("/api/auth/login")
async def debug_api_auth_login(request: Request):
    from app.database import SessionLocal
    from app.services.auth import authenticate_user
    from app.utils.security import create_access_token

    try:
        body = await request.json()
        print("DEBUG LOGIN PAYLOAD:", body)
    except Exception as e:
        body = await request.body()
        print("DEBUG LOGIN PAYLOAD (raw):", body.decode("utf-8"))
        return JSONResponse({"success": False, "message": "Invalid JSON"}, status_code=400)
    
    login_id = body.get("mobile") or body.get("username")
    password = body.get("password")
    
    if not login_id or not password:
        return JSONResponse({"success": False, "message": "Username/mobile and password required"}, status_code=400)
        
    db = SessionLocal()
    try:
        user = authenticate_user(db, login_id, password)
        if not user:
            print(f"Auth failed for user {login_id}")
            return JSONResponse({"success": False, "message": "Invalid credentials"}, status_code=401)
        
        token = create_access_token({"sub": str(user.id), "role": user.role.value})
        response_data = {
            "success": True,
            "data": {
                "access_token": token,
                "token_type": "bearer",
                "user": {
                    "id": user.id,
                    "username": user.username,
                    "full_name": user.full_name,
                    "role": user.role.value
                }
            }
        }
        print("Auth success, response data:", response_data)
        return JSONResponse(response_data)
    finally:
        db.close()




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
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Insufficient permissions"}, status_code=403)
    db = SessionLocal()
    try:
        user = get_current_web_user(request, db)
    finally:
        db.close()
    return _templates.TemplateResponse(
        "errors/403.html", {"request": request, "current_user": user}, status_code=403
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
        "errors/404.html", {"request": request, "current_user": user}, status_code=404
    )
