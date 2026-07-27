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
    query = db.query(VisitRecord)
    if user_id:
        query = query.filter(VisitRecord.user_id == int(user_id))
    if is_joint == "yes":
        query = query.filter(VisitRecord.is_joint_visit == True)
    elif is_joint == "no":
        query = query.filter(VisitRecord.is_joint_visit == False)

    query = query.order_by(VisitRecord.visit_time.desc())
    pagination = paginate(query, page)
    reps = db.query(User).filter(User.role == UserRole.field_rep, User.is_active == True).order_by(User.full_name).all()
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
        db.query(User)
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
):
    today = date.today().isoformat()
    selected_date = map_date or today

    # Check-ins for the day
    ts_query = db.query(Timesheet).filter(Timesheet.work_date == selected_date)
    if user_id:
        ts_query = ts_query.filter(Timesheet.user_id == int(user_id))
    timesheets = ts_query.all()

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
        db.query(VisitRecord)
        .filter(VisitRecord.visit_time >= f"{selected_date} 00:00:00")
        .filter(VisitRecord.visit_time <= f"{selected_date} 23:59:59")
    )
    if user_id:
        vr_query = vr_query.filter(VisitRecord.user_id == int(user_id))
    visits = vr_query.all()

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
    outlets = (
        db.query(Outlet)
        .filter(Outlet.status == OutletStatus.active)
        .filter(Outlet.gps_lat.isnot(None))
        .filter(Outlet.gps_lng.isnot(None))
        .all()
    )
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
        "checkins": checkins,
        "visits": visit_markers,
        "outlets": outlet_markers,
    })
