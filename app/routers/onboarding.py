import os
import re
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, File, UploadFile, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, get_current_web_user
from app.models.user import User, UserRole
from app.services.auth import is_system_onboarded, complete_system_onboarding
from app.utils.backup_service import BACKUP_DIR, list_existing_backups
from app.utils.flash import set_flash_success, set_flash_error, get_flash

logger = logging.getLogger(__name__)

from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse

router = APIRouter(prefix="/onboarding", tags=["onboarding"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def onboarding_page(
    request: Request,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_current_web_user),
):
    if is_system_onboarded(db):
        if user:
            return RedirectResponse("/dashboard", status_code=302)
        return RedirectResponse("/login", status_code=302)

    backups = list_existing_backups()
    return templates.TemplateResponse("auth/onboarding.html", {
        "request": request,
        "existing_backups": backups,
        "error": None,
        "form_data": None,
    })


@router.post("")
async def onboarding_submit(
    request: Request,
    db: Session = Depends(get_db),
    username: str = Form(...),
    full_name: str = Form(...),
    email: str = Form(...),
    phone: str = Form(...),
    password: str = Form(...),
    confirm_password: str = Form(...),
    restore_choice: str = Form("none"),
    selected_backup: Optional[str] = Form(default=None),
    backup_file: Optional[UploadFile] = File(default=None),
):
    form_data = {
        "username": username,
        "full_name": full_name,
        "email": email,
        "phone": phone,
    }

    err = None
    if not username or not username.strip():
        err = "Admin username is required."
    elif not email or not email.strip():
        err = "Admin email address is required."
    elif not phone or not re.match(r"^\d{10}$", phone.strip()):
        err = "Phone number must be exactly 10 digits."
    elif not password or len(password) < 6:
        err = "Password must be at least 6 characters long."
    elif password != confirm_password:
        err = "Passwords do not match."

    if err:
        return templates.TemplateResponse("auth/onboarding.html", {
            "request": request,
            "existing_backups": list_existing_backups(),
            "error": err,
            "form_data": form_data,
        })

    target_backup_filepath = None

    # Handle backup restoration choice
    if restore_choice == "existing" and selected_backup:
        candidate = os.path.join(BACKUP_DIR, os.path.basename(selected_backup))
        if (
            os.path.basename(selected_backup) == selected_backup
            and os.path.exists(candidate)
            and candidate.endswith(".sql.enc")
        ):
            target_backup_filepath = candidate
        else:
            err = f"Selected backup file '{selected_backup}' not found."

    elif restore_choice == "upload" and backup_file and backup_file.filename:
        if not backup_file.filename.endswith(".sql.enc"):
            err = "Uploaded backup must be an encrypted .sql.enc Safar backup."
        else:
            os.makedirs(BACKUP_DIR, exist_ok=True)
            upload_filename = f"safar_upload_{os.path.basename(backup_file.filename)}"
            upload_filepath = os.path.join(BACKUP_DIR, upload_filename)
            contents = await backup_file.read()
            if not contents or len(contents) > 1024 * 1024 * 1024:
                err = "Encrypted backup must be non-empty and no larger than 1 GB."
            else:
                with open(upload_filepath, "wb") as buffer:
                    buffer.write(contents)
                os.chmod(upload_filepath, 0o600)
                target_backup_filepath = upload_filepath

    if err:
        return templates.TemplateResponse("auth/onboarding.html", {
            "request": request,
            "existing_backups": list_existing_backups(),
            "error": err,
            "form_data": form_data,
        })

    try:
        admin_user = complete_system_onboarding(
            db=db,
            username=username.strip(),
            full_name=full_name.strip(),
            email=email.strip(),
            phone=phone.strip(),
            password=password,
            backup_file_path=target_backup_filepath,
        )
    except (ValueError, Exception) as exc:
        logger.error("Onboarding error: %s", exc, exc_info=True)
        return templates.TemplateResponse("auth/onboarding.html", {
            "request": request,
            "existing_backups": list_existing_backups(),
            "error": f"Onboarding failed: {exc}",
            "form_data": form_data,
        })

    request.session["user_id"] = admin_user.id
    set_flash_success(request, f"System onboarding completed successfully! Welcome to Safar SFA Enterprise, {admin_user.full_name}.")
    return RedirectResponse("/dashboard", status_code=302)
