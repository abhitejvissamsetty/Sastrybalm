"""
Attendance router — Split-pane detail view showing activities alongside timesheet approval.
"""
from datetime import date, datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.attendance import Attendance, ApprovalStatus, AttendanceType
from app.models.order import Order
from app.models.payment import Payment
from app.models.material_request import MaterialRequest
from app.models.asset_capitalization import AssetCapitalization
from app.models.timesheet import Timesheet, TimesheetApproval, VisitRecord
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/tracking/attendance", tags=["attendance"])
templates = Jinja2Templates(directory="app/templates")

_ADMIN_MANAGER = require_web_roles(UserRole.admin, UserRole.territory_manager)


@router.get("", response_class=HTMLResponse)
async def attendance_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    approval: str = Query(default=""),
    att_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Attendance)
    if current_user.role == UserRole.field_rep:
        query = query.filter(Attendance.user_id == current_user.id)
    if approval and approval in [s.value for s in ApprovalStatus]:
        query = query.filter(Attendance.approval_status == approval)
    if att_type and att_type in [t.value for t in AttendanceType]:
        query = query.filter(Attendance.attendance_type == att_type)
    query = query.order_by(Attendance.date.desc())
    pagination = paginate(query, page)
    return templates.TemplateResponse("attendance/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "approval": approval, "att_type": att_type,
        "ApprovalStatus": ApprovalStatus, "AttendanceType": AttendanceType,
        **get_flash(request),
    })


@router.get("/{att_id}", response_class=HTMLResponse)
async def attendance_detail(
    att_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    att = db.query(Attendance).filter(Attendance.id == att_id).first()
    if not att:
        set_flash_error(request, "Attendance record not found.")
        return RedirectResponse("/tracking/attendance", status_code=302)

    user = att.user
    att_date = att.date

    # Activity summary — Left pane
    timesheets = db.query(Timesheet).filter(
        Timesheet.user_id == user.id, Timesheet.work_date == att_date,
    ).all()

    visits = db.query(VisitRecord).filter(
        VisitRecord.user_id == user.id,
        func.date(VisitRecord.visit_time) == att_date,
    ).all()

    orders = db.query(Order).filter(
        Order.user_id == user.id, Order.order_date == att_date,
    ).all()

    payments = db.query(Payment).filter(
        Payment.user_id == user.id,
        func.date(Payment.collected_at) == att_date,
    ).all()

    mrs = db.query(MaterialRequest).filter(
        MaterialRequest.user_id == user.id,
        func.date(MaterialRequest.created_at) == att_date,
    ).all()

    acs = db.query(AssetCapitalization).filter(
        AssetCapitalization.user_id == user.id,
        func.date(AssetCapitalization.created_at) == att_date,
    ).all()

    # Calculate Timesheet Hours
    ts_hours = 0.0
    for ts in timesheets:
        if ts.hours_worked:
            ts_hours += ts.hours_worked

    # Calculate System Hours (Checkout - Checkin)
    sys_hours = 0.0
    if att.checkin_time and att.checkout_time:
        sys_hours = (att.checkout_time - att.checkin_time).total_seconds() / 3600.0

    # Calculate Activity-based Hours (earliest timestamp to latest timestamp)
    all_timestamps = []
    for v in visits:
        if v.visit_time:
            all_timestamps.append(v.visit_time)
    for o in orders:
        if o.created_at:
            all_timestamps.append(o.created_at)
    for p in payments:
        if p.collected_at:
            all_timestamps.append(p.collected_at)
    for mr in mrs:
        if mr.created_at:
            all_timestamps.append(mr.created_at)
    for ac in acs:
        if ac.created_at:
            all_timestamps.append(ac.created_at)

    act_hours = 0.0
    if len(all_timestamps) >= 2:
        earliest = min(all_timestamps)
        latest = max(all_timestamps)
        act_hours = (latest - earliest).total_seconds() / 3600.0
    elif len(all_timestamps) == 1:
        act_hours = 0.5  # default estimate for single checkin/order

    # Suggestion logic
    max_hours = max(ts_hours, sys_hours, act_hours)
    if max_hours >= 6.0:
        sug_type = AttendanceType.full_day
    elif max_hours >= 3.0:
        sug_type = AttendanceType.half_day
    else:
        sug_type = AttendanceType.absent

    # Update database record
    att.timesheet_hours = round(ts_hours, 2)
    att.total_hours = round(sys_hours, 2)
    att.activity_hours = round(act_hours, 2)
    att.suggested_type = sug_type
    db.commit()

    return templates.TemplateResponse("attendance/detail.html", {
        "request": request, "current_user": current_user,
        "att": att, "timesheets": timesheets, "visits": visits,
        "orders": orders, "payments": payments,
        "material_requests": mrs, "asset_capitalizations": acs,
        "ApprovalStatus": ApprovalStatus, "AttendanceType": AttendanceType,
        "TimesheetApproval": TimesheetApproval,
        **get_flash(request),
    })


@router.post("/{att_id}/approve")
async def attendance_approve(
    att_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    attendance_type: str = Form(...),
):
    att = db.query(Attendance).filter(Attendance.id == att_id).first()
    if att and att.approval_status == ApprovalStatus.pending:
        try:
            att.attendance_type = AttendanceType(attendance_type)
        except ValueError:
            att.attendance_type = AttendanceType.full_day
        att.approval_status = ApprovalStatus.approved
        att.approved_by_id = current_user.id
        att.approved_at = datetime.now()
        db.commit()
        set_flash_success(request, f"Attendance approved as {att.type_display}.")
    return RedirectResponse(f"/tracking/attendance/{att_id}", status_code=302)


@router.post("/{att_id}/reject")
async def attendance_reject(
    att_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    reason: str = Form(default=""),
):
    att = db.query(Attendance).filter(Attendance.id == att_id).first()
    if att and att.approval_status == ApprovalStatus.pending:
        att.approval_status = ApprovalStatus.rejected
        att.rejection_reason = reason or None
        db.commit()
        set_flash_error(request, "Attendance rejected.")
    return RedirectResponse(f"/tracking/attendance/{att_id}", status_code=302)


@router.post("/{att_id}/reset-checkout")
async def attendance_reset_checkout(
    att_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
):
    att = db.query(Attendance).filter(Attendance.id == att_id).first()
    if not att:
        set_flash_error(request, "Attendance record not found.")
        return RedirectResponse("/tracking/attendance", status_code=302)

    from app.models.timesheet import TimesheetStatus
    att.checkout_time = None
    # Reset any timesheets for that day
    timesheets = db.query(Timesheet).filter(
        Timesheet.user_id == att.user_id,
        Timesheet.work_date == att.date,
    ).all()
    for ts in timesheets:
        ts.status = TimesheetStatus.open
        ts.checkout_time = None
        ts.checkout_lat = None
        ts.checkout_lng = None
        ts.checkout_address = None

    db.commit()
    set_flash_success(request, f"Checkout reset successfully for {att.user.full_name}. They can now login / checkin again today.")
    return RedirectResponse(f"/tracking/attendance/{att_id}", status_code=302)



@router.post("/timesheets/{ts_id}/approve")
async def timesheet_approve(
    ts_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
):
    ts = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
    if ts and ts.approval_status == TimesheetApproval.pending:
        ts.approval_status = TimesheetApproval.approved
        ts.approved_by_id = current_user.id
        ts.approved_at = datetime.now()
        db.commit()
        set_flash_success(request, "Timesheet approved.")
    return RedirectResponse(request.headers.get("referer", "/tracking/attendance"), status_code=302)


@router.post("/timesheets/{ts_id}/reject")
async def timesheet_reject(
    ts_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    reason: str = Form(default=""),
):
    ts = db.query(Timesheet).filter(Timesheet.id == ts_id).first()
    if ts:
        ts.approval_status = TimesheetApproval.rejected
        ts.rejection_reason = reason or None
        db.commit()
        set_flash_error(request, "Timesheet rejected.")
    return RedirectResponse(request.headers.get("referer", "/tracking/attendance"), status_code=302)
