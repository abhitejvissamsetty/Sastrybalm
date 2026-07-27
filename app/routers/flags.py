"""
Auto-Flags router — Admin view of all flagged activities with rating capability.
"""
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.auto_flag import AutoFlag, FlagSeverity, FlagStatus, FlagType
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/action-center/flags", tags=["auto-flags"])
templates = Jinja2Templates(directory="app/templates")

_ADMIN_MANAGER = require_web_roles(UserRole.admin, UserRole.territory_manager)


@router.get("", response_class=HTMLResponse)
async def flag_list(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    severity: str = Query(default=""),
    flag_type: str = Query(default=""),
    status: str = Query(default="open"),
    page: int = Query(default=1, ge=1),
):
    query = db.query(AutoFlag)
    if severity and severity in [s.value for s in FlagSeverity]:
        query = query.filter(AutoFlag.severity == severity)
    if flag_type and flag_type in [t.value for t in FlagType]:
        query = query.filter(AutoFlag.flag_type == flag_type)
    if status and status in [s.value for s in FlagStatus]:
        query = query.filter(AutoFlag.status == status)
    query = query.order_by(AutoFlag.created_at.desc())
    pagination = paginate(query, page)
    return templates.TemplateResponse("flags/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination,
        "severity": severity, "flag_type": flag_type, "status": status,
        "FlagSeverity": FlagSeverity, "FlagType": FlagType, "FlagStatus": FlagStatus,
        **get_flash(request),
    })


@router.post("/{flag_id}/review")
async def flag_review(
    flag_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    admin_rating: int = Form(...),
    new_status: str = Form(default="reviewed"),
    review_notes: Optional[str] = Form(default=None),
):
    flag = db.query(AutoFlag).filter(AutoFlag.id == flag_id).first()
    if not flag:
        set_flash_error(request, "Flag not found.")
        return RedirectResponse("/flags", status_code=302)

    # Clamp rating 1-5
    flag.admin_rating = max(1, min(5, admin_rating))
    try:
        flag.status = FlagStatus(new_status)
    except ValueError:
        flag.status = FlagStatus.reviewed
    flag.reviewed_by_id = current_user.id
    flag.reviewed_at = datetime.now()
    flag.review_notes = review_notes or None
    db.commit()

    set_flash_success(request, f"Flag rated {flag.admin_rating}/5 and marked {flag.status.value}.")
    return RedirectResponse("/action-center/flags", status_code=302)


@router.post("/{flag_id}/escalate")
async def flag_escalate(
    flag_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    review_notes: Optional[str] = Form(default=None),
):
    flag = db.query(AutoFlag).filter(AutoFlag.id == flag_id).first()
    if flag:
        flag.status = FlagStatus.escalated
        flag.reviewed_by_id = current_user.id
        flag.reviewed_at = datetime.now()
        flag.review_notes = review_notes or None
        db.commit()
        set_flash_success(request, "Flag escalated.")
    return RedirectResponse("/flags", status_code=302)
