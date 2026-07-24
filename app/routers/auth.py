from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_current_web_user, get_db
from app.models.user import User
from app.services.auth import (authenticate_user, generate_and_send_user_otp,
                               verify_user_otp)

router = APIRouter(tags=["auth"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/login", response_class=HTMLResponse)
async def login_page(
    request: Request,
    user: Optional[User] = Depends(get_current_web_user),
):
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
    user = authenticate_user(db, username, password)
    if not user:
        request.session["_flash_error"] = "Invalid username or password. Note: Admin authenticates via .env credentials."
        return RedirectResponse("/login", status_code=302)
    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@router.post("/auth/request-otp", response_class=HTMLResponse)
async def request_otp(
    request: Request,
    email: str = Form(...),
    db: Session = Depends(get_db),
):
    res = generate_and_send_user_otp(db, email)
    if not res["success"]:
        return templates.TemplateResponse("auth/login.html", {
            "request": request,
            "error": res["error"],
            "otp_step": False,
        })

    info_msg = f"OTP verification code sent to {res['email']}."
    if not res.get("email_sent"):
        info_msg += f" (Test Mode: Code is {res['otp_code']})"

    return templates.TemplateResponse("auth/login.html", {
        "request": request,
        "info": info_msg,
        "otp_step": True,
        "email": res["email"],
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
            "error": "Invalid or expired OTP code. Please try again.",
            "otp_step": True,
            "email": email,
        })

    request.session["user_id"] = user.id
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/logout")
async def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=302)
