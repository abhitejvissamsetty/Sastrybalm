from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_current_web_user, get_db
from app.models.user import User, UserRole
from app.services.auth import (
    authenticate_user,
    generate_and_send_user_otp,
    verify_user_otp,
)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


from app.services.auth import is_system_onboarded


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_web_user),
    db: Session = Depends(get_db),
):
    if not is_system_onboarded(db):
        return RedirectResponse("/onboarding", status_code=302)

    if user:
        return RedirectResponse("/dashboard", status_code=302)
    error = request.session.pop("_flash_error", None)
    info = request.session.pop("_flash_info", None)
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "error": error,
        "info": info,
        "otp_step": False,
    })


@router.post("/login")
async def login(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    if not is_system_onboarded(db):
        return RedirectResponse("/onboarding", status_code=302)

    user = authenticate_user(db, username, password)
    if not user:
        request.session["_flash_error"] = "Invalid admin username or password."
        return RedirectResponse("/login", status_code=302)

    # Block field reps from web dashboard — mobile app only
    if user.role == UserRole.field_rep:
        request.session["_flash_error"] = "Field Representatives are not permitted to access the web dashboard. Please use the mobile app."
        return RedirectResponse("/login", status_code=302)

    request.state.audit_user_id = user.id
    request.state.audit_user_role = user.role.value
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@router.post("/auth/request-otp", response_class=HTMLResponse)
async def request_otp(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    result = generate_and_send_user_otp(db, email)
    if not result["success"]:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": result["error"],
            "otp_step": False,
        })
    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "info": "OTP verification code sent to your registered email.",
        "otp_step": True,
        "email": result["email"],
    })


@router.post("/auth/verify-otp")
async def verify_otp(
    request: Request,
    email: str = Form(...),
    otp_code: str = Form(...),
    db: Session = Depends(get_db),
):
    user = verify_user_otp(db, email, otp_code)
    if not user:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Invalid or expired OTP code.",
            "otp_step": True,
            "email": email,
        })
    if user.role == UserRole.field_rep:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": "Field Representatives must use the mobile app.",
            "otp_step": False,
        })
    request.state.audit_user_id = user.id
    request.state.audit_user_role = user.role.value
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    response = RedirectResponse("/login", status_code=302)
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, max-age=0, private"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response
