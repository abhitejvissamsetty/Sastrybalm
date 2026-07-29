from datetime import datetime, date, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import (get_db, require_web_auth, require_web_roles,
                            require_restricted_module_web_access)
from app.models.order import Order, OrderItem, OrderStatus
from app.models.timesheet import (Timesheet, TimesheetApproval, TimesheetComment,
                                  TimesheetLineItem, TimesheetStatus, VisitRecord)
from app.models.user import User, UserRole
from app.services.timesheet_service import get_or_create_open_timesheet
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.utils.timezone import ist_now, ist_today
from app.services.access_control import (
    require_timesheet_access,
    scope_employee_record_query,
    scope_user_query,
    scope_visit_query,
)

router = APIRouter(prefix="/operations/timesheets", tags=["timesheets"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def timesheet_list(
    request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
    tab: str = Query(default="non_submitted"), # non_submitted or submitted
    user_id: str = Query(default=""),
    work_date: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = scope_employee_record_query(db.query(Timesheet), Timesheet, current_user, db)
    if user_id:
        query = query.filter(Timesheet.user_id == int(user_id))

    if tab == "submitted":
        # Submitted timesheets are closed or pending/approved/rejected
        query = query.filter(Timesheet.submitted_at.isnot(None))
    else:
        # Non-submitted timesheets (open or draft)
        query = query.filter(Timesheet.submitted_at.is_(None))

    if work_date:
        query = query.filter(Timesheet.work_date == work_date)

    query = query.order_by(Timesheet.work_date.desc(), Timesheet.checkin_time.desc())
    pagination = paginate(query, page)

    reps = []
    if current_user.role.value in ["admin", "manager", "territory_manager"]:
        reps = scope_user_query(
            db.query(User), current_user, db, include_self=False
        ).filter(User.role == UserRole.field_rep, User.is_active == True).order_by(User.full_name).all()

    # Check if user has an active open timesheet today
    today_ts = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.work_date == ist_today()
    ).first()

    return templates.TemplateResponse("timesheets/list.html", {
        "request": request,
        "current_user": current_user,
        "pagination": pagination,
        "tab": tab,
        "user_id": user_id,
        "work_date": work_date,
        "reps": reps,
        "today_ts": today_ts,
        "TimesheetStatus": TimesheetStatus,
        "TimesheetApproval": TimesheetApproval,
        **get_flash(request),
    })


@router.post("/start-workshift")
async def start_workshift(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    """
    Start Workshift handler: creates a non-submitted timesheet for today.
    """
    ts = get_or_create_open_timesheet(db, current_user.id)
    db.commit()
    set_flash_success(request, f"Workshift started for today ({ts.work_date}). Timesheet created in Non Submitted view.")
    return RedirectResponse(f"/operations/timesheets/{ts.id}", status_code=302)


@router.get("/{ts_id}", response_class=HTMLResponse)
async def timesheet_detail(
    ts_id: int,
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    try:
        item = require_timesheet_access(db, current_user, ts_id)
    except HTTPException:
        set_flash_error(request, "Timesheet not found.")
        return RedirectResponse("/operations/timesheets", status_code=302)

    # 1. Login/Logout Session Pairs with 23:59:59 auto cutoff logic
    checkin = item.checkin_time
    checkout = item.checkout_time
    is_unclosed = checkin and not checkout
    cutoff_time = datetime.combine(item.work_date, datetime.max.time().replace(microsecond=0))

    session_pairs = []
    if checkin:
        eff_checkout = checkout or cutoff_time
        session_pairs.append({
            "checkin": checkin,
            "checkout": eff_checkout,
            "is_unclosed": is_unclosed,
            "cutoff_used": is_unclosed,
            "duration_hours": round((eff_checkout - checkin).total_seconds() / 3600, 2),
        })

    # 2. Productivity Gist Summary
    visits_count = len(item.visits)
    joint_visits_count = sum(1 for v in item.visits if v.is_joint_visit)
    orders_count = db.query(func.count(Order.id)).filter(
        Order.user_id == item.user_id,
        Order.order_date == item.work_date
    ).scalar() or 0

    rev_q = db.query(
        func.coalesce(
            func.sum(OrderItem.unit_price * OrderItem.quantity * (1 - OrderItem.discount_pct / 100)),
            0
        )
    ).join(Order, Order.id == OrderItem.order_id).filter(
        Order.user_id == item.user_id,
        Order.order_date == item.work_date,
        Order.status.in_([OrderStatus.confirmed, OrderStatus.dispatched, OrderStatus.delivered])
    )
    revenue_sum = round(float(rev_q.scalar() or 0), 2)

    productivity_gist = {
        "visits_count": visits_count,
        "joint_visits_count": joint_visits_count,
        "orders_count": orders_count,
        "revenue_sum": revenue_sum,
        "has_auto_activity": visits_count > 0 or orders_count > 0,
    }

    # 3. Days elapsed check for 7-day recall restriction
    days_old = (ist_today() - item.work_date).days
    can_edit_or_recall = days_old <= 7

    return templates.TemplateResponse("timesheets/detail.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "session_pairs": session_pairs,
        "productivity_gist": productivity_gist,
        "can_edit_or_recall": can_edit_or_recall,
        "days_old": days_old,
        "TimesheetStatus": TimesheetStatus,
        "TimesheetApproval": TimesheetApproval,
        **get_flash(request),
    })


@router.post("/{ts_id}/line-items")
async def add_manual_line_item(
    ts_id: int,
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    category: str = Form(...), # Office Work, Distributor Meetings, Public Campaigning
    start_time_str: str = Form(...),
    end_time_str: str = Form(...),
    notes: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
):
    """
    Manually add line items outside automated logging, but within checkin and checkout times.
    Categories allowed: Office Work, Distributor Meetings, Public Campaigning.
    """
    try:
        ts = require_timesheet_access(db, current_user, ts_id)
    except HTTPException:
        ts = None
    if not ts or ts.user_id != current_user.id:
        set_flash_error(request, "Timesheet not found or access denied.")
        return RedirectResponse("/operations/timesheets", status_code=302)

    if ts.submitted_at and ts.approval_status != TimesheetApproval.pending:
        set_flash_error(request, "Submitted timesheets cannot be edited unless recalled first.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    if (ist_today() - ts.work_date).days > 7:
        set_flash_error(request, "Timesheets older than 7 days cannot be edited.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    if category in ["Retailing Work", "Joint Working"]:
        set_flash_error(request, "Retailing Work and Joint Working line items are automatically logged and cannot be added manually.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    try:
        start_time = datetime.fromisoformat(start_time_str)
        end_time = datetime.fromisoformat(end_time_str)
    except Exception:
        set_flash_error(request, "Invalid start or end time format.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    if start_time >= end_time:
        set_flash_error(request, "Start time must be strictly before end time.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    image_url = None
    if image and image.filename:
        file_bytes = await image.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            image_url = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=image.filename,
                folder_prefix="timesheets/line_items",
                content_type=image.content_type or "image/jpeg",
                bucket_type="permanent",
            )

    item = TimesheetLineItem(
        timesheet_id=ts.id,
        category=category,
        start_time=start_time,
        end_time=end_time,
        is_automated=False,
        notes=notes or None,
        image_url=image_url,
    )
    db.add(item)
    db.commit()

    set_flash_success(request, f"Manual line item '{category}' added to timesheet.")
    return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)


@router.post("/{ts_id}/submit")
async def submit_timesheet(
    ts_id: int,
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    """
    Submits timesheet from detail view. Increments version and locks editing.
    """
    try:
        ts = require_timesheet_access(db, current_user, ts_id)
    except HTTPException:
        ts = None
    if not ts:
        set_flash_error(request, "Timesheet not found.")
        return RedirectResponse("/operations/timesheets", status_code=302)

    # Self-editing ONLY restriction: Manager cannot submit on behalf of subordinate
    if ts.user_id != current_user.id:
        set_flash_error(request, "Only the user can submit their own timesheet. Managers cannot submit on behalf of subordinates.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    if (ist_today() - ts.work_date).days > 7:
        set_flash_error(request, "Timesheets older than 7 days cannot be modified.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    ts.submitted_at = ist_now()
    ts.status = TimesheetStatus.closed
    ts.approval_status = TimesheetApproval.pending
    ts.version += 1
    db.commit()

    set_flash_success(request, f"Timesheet for {ts.work_date} (v{ts.version}) submitted successfully for manager approval.")
    return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)


@router.post("/{ts_id}/recall")
async def recall_timesheet(
    ts_id: int,
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    submitted_version: int = Form(...),
):
    """
    Recall submitted timesheet for self-editing if:
    1) Status is pending (not approved/rejected)
    2) Submitted version matches DB version (optimistic lock against manager approval corruption)
    3) Age <= 7 days
    """
    try:
        ts = require_timesheet_access(db, current_user, ts_id)
    except HTTPException:
        ts = None
    if not ts:
        set_flash_error(request, "Timesheet not found.")
        return RedirectResponse("/operations/timesheets", status_code=302)

    if ts.user_id != current_user.id:
        set_flash_error(request, "You can only recall your own timesheets.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    if (ist_today() - ts.work_date).days > 7:
        set_flash_error(request, "Timesheets older than 7 days cannot be recalled.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    if ts.approval_status != TimesheetApproval.pending:
        set_flash_error(request, "Cannot recall timesheet that has already been approved or rejected by a manager.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    # Optimistic locking version check
    if ts.version != submitted_version:
        set_flash_error(request, f"Recall failed: Timesheet version mismatch (Current v{ts.version} vs Submitted v{submitted_version}). The record may have been modified by a manager.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    # Perform recall: reset submitted_at and reopen
    ts.submitted_at = None
    ts.status = TimesheetStatus.open
    db.commit()

    set_flash_success(request, f"Timesheet recalled successfully. You can now edit and re-submit.")
    return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)


@router.post("/{ts_id}/comments")
async def add_timesheet_comment(
    ts_id: int,
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    comment: str = Form(...),
):
    """
    Adds a comment on a submitted timesheet for user-manager discussion.
    """
    try:
        ts = require_timesheet_access(db, current_user, ts_id)
    except HTTPException:
        ts = None
    if not ts:
        set_flash_error(request, "Timesheet not found.")
        return RedirectResponse("/operations/timesheets", status_code=302)

    if not comment.strip():
        set_flash_error(request, "Comment cannot be empty.")
        return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)

    tc = TimesheetComment(
        timesheet_id=ts.id,
        user_id=current_user.id,
        comment=comment.strip()
    )
    db.add(tc)
    db.commit()

    set_flash_success(request, "Comment added.")
    return RedirectResponse(f"/operations/timesheets/{ts_id}", status_code=302)


@router.get("/visits/all", response_class=HTMLResponse)
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
    reps = (
        scope_user_query(db.query(User), current_user, db, include_self=False)
        .filter(User.role == UserRole.field_rep, User.is_active == True)
        .order_by(User.full_name)
        .all()
    )
    return templates.TemplateResponse("timesheets/visits.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "user_id": user_id, "is_joint": is_joint, "reps": reps,
        **get_flash(request),
    })
