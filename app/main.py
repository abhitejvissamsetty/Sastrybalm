from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

from app.routers import auth, dashboard, geography, positions, beats, outlets, products, users, company
from app.routers import orders, payments, expenses, timesheets, tracking, analytics, material_requests
from app.routers import asset_capitalizations, vendors, attendance, approvals, flags, inventory
from app.routers import settings as settings_router
from app.routers.api import auth as api_auth
from app.routers.api import master as api_master
from app.routers.api import operations as api_operations
from app.routers.api import webhooks as api_webhooks
from app.scheduler import start_scheduler, scheduler

@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        from db_migrate import run_migrations
        run_migrations()
    except Exception as e:
        print(f"Lifespan migration error: {e}")
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

_templates = Jinja2Templates(directory="app/templates")

from app.routers import backup, channel_partners, warehouses

# Web routers
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

# API routers
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


@app.exception_handler(403)
async def forbidden_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Insufficient permissions"}, status_code=403)
    return _templates.TemplateResponse(
        "errors/403.html", {"request": request, "current_user": None}, status_code=403
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    if request.url.path.startswith("/api/"):
        return JSONResponse({"detail": "Not found"}, status_code=404)
    return _templates.TemplateResponse(
        "errors/404.html", {"request": request, "current_user": None}, status_code=404
    )
