from datetime import date

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.outlet import Outlet, OutletStatus
from app.models.timesheet import Timesheet, VisitRecord
from app.models.user import User, UserRole
from app.utils.flash import get_flash
from app.utils.pagination import paginate
from app.services.access_control import (
    scope_employee_record_query,
    scope_outlet_query,
    scope_user_query,
    scope_visit_query,
)

router = APIRouter(prefix="/tracking", tags=["tracking"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/visits", response_class=HTMLResponse)
async def visit_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    user_id: str = Query(default=""),
    is_joint: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = scope_visit_query(db.query(VisitRecord), current_user, db)
    if user_id:
        query = query.filter(VisitRecord.user_id == int(user_id))
    if is_joint == "yes":
        query = query.filter(VisitRecord.is_joint_visit == True)
    elif is_joint == "no":
        query = query.filter(VisitRecord.is_joint_visit == False)

    query = query.order_by(VisitRecord.visit_time.desc())
    pagination = paginate(query, page)
    reps = scope_user_query(
        db.query(User), current_user, db, include_self=False
    ).filter(User.role == UserRole.field_rep, User.is_active == True).order_by(User.full_name).all()
    return templates.TemplateResponse("timesheets/visits.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "user_id": user_id, "is_joint": is_joint, "reps": reps,
        **get_flash(request),
    })


@router.get("/map", response_class=HTMLResponse)
async def gps_map_view(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    map_date: str = Query(default=""),
    user_id: str = Query(default=""),
):
    today = date.today().isoformat()
    selected_date = map_date or today
    reps = (
        scope_user_query(db.query(User), current_user, db, include_self=False)
        .filter(User.role == UserRole.field_rep, User.is_active == True)
        .order_by(User.full_name)
        .all()
    )
    return templates.TemplateResponse("tracking/map.html", {
        "request": request,
        "current_user": current_user,
        "reps": reps,
        "selected_date": selected_date,
        "user_id": user_id,
        **get_flash(request),
    })


@router.get("/map/data")
async def gps_map_data(
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    map_date: str = Query(default=""),
    user_id: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=100),
):
    today = date.today().isoformat()
    selected_date = map_date or today

    # Check-ins for the day
    ts_query = scope_employee_record_query(
        db.query(Timesheet), Timesheet, current_user, db
    ).filter(Timesheet.work_date == selected_date)
    if user_id:
        ts_query = ts_query.filter(Timesheet.user_id == int(user_id))
    timesheet_total = ts_query.count()
    timesheets = ts_query.order_by(Timesheet.id).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    checkins = []
    for ts in timesheets:
        if ts.checkin_lat and ts.checkin_lng:
            checkins.append({
                "id": ts.id,
                "lat": ts.checkin_lat,
                "lng": ts.checkin_lng,
                "rep": ts.user.full_name if ts.user else "—",
                "time": ts.checkin_time.strftime("%H:%M") if ts.checkin_time else "—",
                "address": ts.checkin_address or "",
                "checkout_lat": ts.checkout_lat,
                "checkout_lng": ts.checkout_lng,
                "checkout_time": ts.checkout_time.strftime("%H:%M") if ts.checkout_time else None,
                "hours": ts.hours_worked,
                "status": ts.status.value,
            })

    # Visit records for the day
    vr_query = (
        scope_visit_query(db.query(VisitRecord), current_user, db)
        .filter(VisitRecord.visit_time >= f"{selected_date} 00:00:00")
        .filter(VisitRecord.visit_time <= f"{selected_date} 23:59:59")
    )
    if user_id:
        vr_query = vr_query.filter(VisitRecord.user_id == int(user_id))
    visit_total = vr_query.count()
    visits = vr_query.order_by(VisitRecord.id).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    visit_markers = []
    for v in visits:
        if v.gps_lat and v.gps_lng:
            visit_markers.append({
                "id": v.id,
                "lat": v.gps_lat,
                "lng": v.gps_lng,
                "rep": v.user.full_name if v.user else "—",
                "outlet": v.outlet.name if v.outlet else "—",
                "time": v.visit_time.strftime("%H:%M"),
                "purpose": v.purpose or "—",
                "distance": v.distance_from_outlet,
                "compliant": (v.distance_from_outlet is None or v.distance_from_outlet <= 200),
            })

    # All approved outlets with GPS coords
    outlet_query = (
        scope_outlet_query(db.query(Outlet), current_user, db)
        .filter(Outlet.status == OutletStatus.active)
        .filter(Outlet.gps_lat.isnot(None))
        .filter(Outlet.gps_lng.isnot(None))
    )
    outlet_total = outlet_query.count()
    outlets = outlet_query.order_by(Outlet.id).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    outlet_markers = [
        {
            "id": o.id,
            "lat": o.gps_lat,
            "lng": o.gps_lng,
            "name": o.name,
            "code": o.code or "",
            "channel": o.channel or "",
        }
        for o in outlets
    ]

    return JSONResponse({
        "page": page,
        "per_page": per_page,
        "total": max(timesheet_total, visit_total, outlet_total),
        "checkins": checkins,
        "visits": visit_markers,
        "outlets": outlet_markers,
    })
