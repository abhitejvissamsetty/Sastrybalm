from typing import Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.timesheet import Timesheet, VisitRecord
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error
from app.utils.pagination import paginate

router = APIRouter(prefix="/timesheets", tags=["timesheets"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def timesheet_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    user_id: str = Query(default=""),
    work_date: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Timesheet)
    if current_user.role == UserRole.field_rep:
        query = query.filter(Timesheet.user_id == current_user.id)
    elif user_id:
        query = query.filter(Timesheet.user_id == int(user_id))
    if work_date:
        query = query.filter(Timesheet.work_date == work_date)
    query = query.order_by(Timesheet.work_date.desc(), Timesheet.checkin_time.desc())
    pagination = paginate(query, page)

    reps = []
    if current_user.role.value in ["admin", "manager"]:
        reps = db.query(User).filter(User.role == UserRole.field_rep, User.is_active == True).order_by(User.full_name).all()

    return templates.TemplateResponse("timesheets/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "user_id": user_id, "work_date": work_date,
        "reps": reps, **get_flash(request),
    })


@router.get("/{ts_id}", response_class=HTMLResponse)
async def timesheet_detail(
    ts_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    q = db.query(Timesheet).filter(Timesheet.id == ts_id)
    if current_user.role == UserRole.field_rep:
        q = q.filter(Timesheet.user_id == current_user.id)
    item = q.first()
    if not item:
        set_flash_error(request, "Timesheet not found.")
        return RedirectResponse("/timesheets", status_code=302)
    return templates.TemplateResponse("timesheets/detail.html", {
        "request": request, "current_user": current_user, "item": item,
    })


@router.get("/visits/all", response_class=HTMLResponse)
async def visit_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    user_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(VisitRecord)
    if user_id:
        query = query.filter(VisitRecord.user_id == int(user_id))
    query = query.order_by(VisitRecord.visit_time.desc())
    pagination = paginate(query, page)
    reps = db.query(User).filter(User.role == UserRole.field_rep, User.is_active == True).order_by(User.full_name).all()
    return templates.TemplateResponse("timesheets/visits.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "user_id": user_id, "reps": reps,
        **get_flash(request),
    })
