"""
Mobile API — Phase 3 Operations
Covers: attendance (timesheet), visits, orders, payments, expenses, material requests.
All endpoints require Bearer JWT auth.
"""
from datetime import date, datetime
from typing import List, Optional

from fastapi import APIRouter, Body, Depends, Form, HTTPException, Query, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.company import CompanyProfile
from app.models.expense import Expense, ExpenseCategory, ExpenseStatus
from app.models.material_request import MaterialRequest, MRStatus
from app.models.order import Order, OrderItem, OrderStatus, FlowType, SyncStatus
from app.services.sync import sync_order_to_connect, sync_order_to_zap
from app.models.outlet import Outlet, OutletStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.product_mapping import ProductAliasMap
from app.models.timesheet import Timesheet, TimesheetStatus, VisitRecord
from app.models.user import User, UserRole
from app.utils.encryption import decrypt
from app.utils.haversine import haversine_distance
from app.utils.ref_generator import mr_number, order_number, payment_ref

router = APIRouter(prefix="/api/v1", tags=["mobile-operations"])


# ── Attendance / Timesheet ─────────────────────────────────────────────────────

@router.post("/attendance/checkin")
async def checkin(
    gps_lat: float,
    gps_lng: float,
    address: Optional[str] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.models.attendance import Attendance, ApprovalStatus
    today = date.today()
    existing = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.work_date == today,
    ).first()
    if existing:
        return {"id": existing.id, "status": existing.status.value, "message": "Already checked in today."}

    # Find or create Attendance record for today
    att = db.query(Attendance).filter(
        Attendance.user_id == current_user.id,
        Attendance.date == today,
    ).first()
    if not att:
        att = Attendance(
            user_id=current_user.id,
            date=today,
            checkin_time=datetime.now(),
            approval_status=ApprovalStatus.pending,
        )
        db.add(att)
        db.flush()
    elif not att.checkin_time:
        att.checkin_time = datetime.now()
        db.flush()

    ts = Timesheet(
        user_id=current_user.id,
        attendance_id=att.id,
        work_date=today,
        checkin_time=datetime.now(),
        checkin_lat=gps_lat,
        checkin_lng=gps_lng,
        checkin_address=address,
        status=TimesheetStatus.open,
    )
    db.add(ts)
    db.commit()
    db.refresh(ts)
    return {"id": ts.id, "status": ts.status.value, "checkin_time": ts.checkin_time.isoformat()}


@router.post("/attendance/checkout")
async def checkout(
    gps_lat: float,
    gps_lng: float,
    address: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.models.attendance import Attendance, AttendanceType
    from app.models.asset_capitalization import AssetCapitalization
    today = date.today()
    ts = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.work_date == today,
        Timesheet.status == TimesheetStatus.open,
    ).first()
    if not ts:
        raise HTTPException(status_code=400, detail="No open timesheet found for today.")

    ts.checkout_time = datetime.now()
    ts.checkout_lat = gps_lat
    ts.checkout_lng = gps_lng
    ts.checkout_address = address
    ts.status = TimesheetStatus.closed
    ts.notes = notes
    db.flush()

    # Find the corresponding Attendance record
    att = None
    if ts.attendance_id:
        att = db.query(Attendance).filter(Attendance.id == ts.attendance_id).first()
    if not att:
        att = db.query(Attendance).filter(
            Attendance.user_id == current_user.id,
            Attendance.date == today,
        ).first()

    if att:
        att.checkout_time = datetime.now()
        db.flush()
        
        # Calculate suggested shift status
        # Get all timesheets, visits, orders, payments, mrs, acs for today
        timesheets = db.query(Timesheet).filter(
            Timesheet.user_id == current_user.id, Timesheet.work_date == today
        ).all()
        visits = db.query(VisitRecord).filter(
            VisitRecord.user_id == current_user.id,
            func.date(VisitRecord.visit_time) == today,
        ).all()
        orders = db.query(Order).filter(
            Order.user_id == current_user.id, Order.order_date == today
        ).all()
        payments = db.query(Payment).filter(
            Payment.user_id == current_user.id,
            func.date(Payment.collected_at) == today,
        ).all()
        mrs = db.query(MaterialRequest).filter(
            MaterialRequest.user_id == current_user.id,
            func.date(MaterialRequest.created_at) == today,
        ).all()
        acs = db.query(AssetCapitalization).filter(
            AssetCapitalization.user_id == current_user.id,
            func.date(AssetCapitalization.created_at) == today,
        ).all()

        # Calculate Timesheet Hours
        ts_hours = 0.0
        for t in timesheets:
            if t.hours_worked:
                ts_hours += t.hours_worked

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
            act_hours = 0.5

        # Suggestion logic
        max_hours = max(ts_hours, sys_hours, act_hours)
        if max_hours >= 6.0:
            sug_type = AttendanceType.full_day
        elif max_hours >= 3.0:
            sug_type = AttendanceType.half_day
        else:
            sug_type = AttendanceType.absent

        att.timesheet_hours = round(ts_hours, 2)
        att.total_hours = round(sys_hours, 2)
        att.activity_hours = round(act_hours, 2)
        att.suggested_type = sug_type
        if not att.attendance_type:
            att.attendance_type = sug_type
            
    db.commit()
    return {
        "id": ts.id,
        "status": ts.status.value,
        "hours_worked": ts.hours_worked,
        "visit_count": ts.visit_count,
    }


@router.get("/attendance/today")
async def attendance_today(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    ts = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.work_date == date.today(),
    ).first()
    if not ts:
        return {"checked_in": False}
    return {
        "checked_in": True,
        "id": ts.id,
        "status": ts.status.value,
        "checkin_time": ts.checkin_time.isoformat() if ts.checkin_time else None,
        "checkout_time": ts.checkout_time.isoformat() if ts.checkout_time else None,
        "visit_count": ts.visit_count,
    }


# ── Visit Records ──────────────────────────────────────────────────────────────

@router.post("/visits")
async def log_visit(
    outlet_id: int,
    gps_lat: float,
    gps_lng: float,
    purpose: Optional[str] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.status == OutletStatus.active).first()
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found.")

    distance = None
    if outlet.gps_lat and outlet.gps_lng:
        distance = haversine_distance(gps_lat, gps_lng, outlet.gps_lat, outlet.gps_lng)

    today = date.today()
    ts = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.work_date == today,
        Timesheet.status == TimesheetStatus.open,
    ).first()

    visit = VisitRecord(
        user_id=current_user.id,
        outlet_id=outlet_id,
        timesheet_id=ts.id if ts else None,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        distance_from_outlet=distance,
        purpose=purpose,
        notes=notes,
    )
    db.add(visit)
    db.flush()

    # Trigger GPS flagging check
    from app.services.auto_flagging import flag_visit_gps
    flag_visit_gps(db, visit)
    db.commit()
    db.refresh(visit)
    return {"id": visit.id, "distance_from_outlet": distance, "visit_time": visit.visit_time.isoformat()}


@router.post("/visits/{visit_id}/checkout")
async def checkout_visit(
    visit_id: int,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    visit = db.query(VisitRecord).filter(
        VisitRecord.id == visit_id,
        VisitRecord.user_id == current_user.id
    ).first()
    if not visit:
        raise HTTPException(status_code=404, detail="Visit record not found.")

    if visit.checkout_time:
        raise HTTPException(status_code=400, detail="Visit already checked out.")

    visit.checkout_time = datetime.now()
    db.flush()

    # Trigger duration flagging check
    from app.services.auto_flagging import flag_visit_duration
    flag = flag_visit_duration(db, visit)
    db.commit()

    return {
        "id": visit.id,
        "checkout_time": visit.checkout_time.isoformat(),
        "duration_minutes": visit.duration_minutes,
        "flagged": flag is not None
    }


# ── Orders ─────────────────────────────────────────────────────────────────────

@router.post("/orders")
async def create_order(
    outlet_id: int,
    items: list[dict],  # [{product_id, quantity, unit_price, gst_rate, discount_pct}]
    beat_id: Optional[int] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.status == OutletStatus.active).first()
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found.")
    if not items:
        raise HTTPException(status_code=400, detail="Order must have at least one item.")

    ord_num = order_number(db, Order)
    o = Order(
        order_number=ord_num,
        outlet_id=outlet_id,
        user_id=current_user.id,
        beat_id=beat_id,
        company_profile_id=current_user.company_profile_id,
        status=OrderStatus.draft,
        notes=notes,
    )
    db.add(o)
    db.flush()

    for it in items:
        db.add(OrderItem(
            order_id=o.id,
            product_id=it["product_id"],
            quantity=it.get("quantity", 1),
            unit_price=it["unit_price"],
            gst_rate=it.get("gst_rate", 0),
            discount_pct=it.get("discount_pct", 0),
        ))
    db.commit()
    db.refresh(o)
    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status.value,
        "total_amount": o.total_amount,
        "item_count": o.item_count,
    }


@router.patch("/orders/{order_id}/submit")
async def submit_order(
    order_id: int,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    o = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found.")
    if o.status != OrderStatus.draft:
        raise HTTPException(status_code=400, detail=f"Cannot submit order in '{o.status.value}' state.")
    o.status = OrderStatus.submitted
    o.sync_status = SyncStatus.pending
    db.commit()

    if o.flow_type == FlowType.connect:
        await sync_order_to_connect(o, db)
    elif o.flow_type == FlowType.zap_invoice:
        await sync_order_to_zap(o, db)

    return {"id": o.id, "order_number": o.order_number, "status": o.status.value}


@router.get("/orders/my")
async def my_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    query = db.query(Order).filter(Order.user_id == current_user.id).order_by(Order.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total, "page": page, "per_page": per_page,
        "items": [
            {
                "id": o.id, "order_number": o.order_number, "status": o.status.value,
                "outlet_name": o.outlet.name if o.outlet else None,
                "total_amount": o.total_amount, "order_date": o.order_date.isoformat(),
            }
            for o in items
        ],
    }


@router.get("/orders/{order_id}")
async def get_order_detail(
    order_id: int,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    o = db.query(Order).filter(Order.id == order_id, Order.user_id == current_user.id).first()
    if not o:
        raise HTTPException(status_code=404, detail="Order not found.")
    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status.value,
        "outlet_name": o.outlet.name if o.outlet else None,
        "total_amount": o.total_amount,
        "order_date": o.order_date.isoformat(),
        "notes": o.notes,
        "items": [
            {
                "product_name": it.product.name if it.product else "Unknown Product",
                "quantity": it.quantity,
                "unit_price": float(it.unit_price),
                "line_total": it.line_total_with_gst,
            }
            for it in o.items
        ],
    }


# ── Payments ───────────────────────────────────────────────────────────────────

@router.post("/payments")
async def collect_payment(
    outlet_id: int,
    amount: float,
    method: str,
    order_id: Optional[int] = None,
    transaction_ref: Optional[str] = None,
    denom_2000: int = 0,
    denom_500: int = 0,
    denom_200: int = 0,
    denom_100: int = 0,
    denom_50: int = 0,
    denom_20: int = 0,
    denom_10: int = 0,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    try:
        pay_method = PaymentMethod(method)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid payment method '{method}'.")

    ref = payment_ref(db, Payment)
    p = Payment(
        payment_ref=ref,
        order_id=order_id,
        outlet_id=outlet_id,
        user_id=current_user.id,
        amount=amount,
        method=pay_method,
        transaction_ref=transaction_ref,
        status=PaymentStatus.collected,
        denom_2000=denom_2000,
        denom_500=denom_500,
        denom_200=denom_200,
        denom_100=denom_100,
        denom_50=denom_50,
        denom_20=denom_20,
        denom_10=denom_10,
    )
    db.add(p)
    db.flush()

    # Trigger payment denomination mismatch check
    from app.services.auto_flagging import flag_payment_mismatch
    flag_payment_mismatch(db, p)
    db.commit()
    db.refresh(p)
    return {"id": p.id, "payment_ref": p.payment_ref, "status": p.status.value}


# ── Expenses ───────────────────────────────────────────────────────────────────

@router.post("/expenses")
async def log_expense(
    category: str,
    amount: float,
    description: Optional[str] = None,
    expense_date: Optional[str] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    try:
        cat = ExpenseCategory(category)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid category '{category}'.")

    exp_date = date.fromisoformat(expense_date) if expense_date else date.today()
    e = Expense(
        user_id=current_user.id,
        category=cat,
        amount=amount,
        description=description,
        expense_date=exp_date,
        status=ExpenseStatus.submitted,
    )
    db.add(e)
    db.commit()
    db.refresh(e)
    return {"id": e.id, "status": e.status.value}


@router.post("/expenses/{expense_id}/receipt")
async def upload_receipt_api(
    expense_id: int,
    request: Request,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Mobile API: upload receipt image for an expense."""
    import os
    import uuid

    from fastapi import UploadFile

    expense = db.query(Expense).filter(
        Expense.id == expense_id,
        Expense.user_id == current_user.id,
    ).first()
    if not expense:
        raise HTTPException(status_code=404, detail="Expense not found.")

    form = await request.form()
    file = form.get("file")
    if not file or not hasattr(file, "filename"):
        raise HTTPException(status_code=400, detail="No file uploaded.")

    # Validate file
    allowed = {".jpg", ".jpeg", ".png", ".pdf"}
    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in allowed:
        raise HTTPException(status_code=400, detail=f"File type not allowed. Use: {', '.join(allowed)}")

    contents = await file.read()
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large. Maximum 5MB.")

    upload_dir = os.path.join("app", "static", "uploads", "receipts")
    os.makedirs(upload_dir, exist_ok=True)

    filename = f"{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(upload_dir, filename)
    with open(filepath, "wb") as f:
        f.write(contents)

    expense.receipt_url = f"/static/uploads/receipts/{filename}"
    db.commit()
    return {"receipt_url": expense.receipt_url}


# ── Material Requests ──────────────────────────────────────────────────────────

@router.post("/material-requests")
async def submit_material_request(
    outlet_id: int,
    description: str,
    category: Optional[str] = None,
    company_profile_id: Optional[int] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id).first()
    if not outlet:
        raise HTTPException(status_code=404, detail="Outlet not found.")

    mr_num = mr_number(db, MaterialRequest)
    mr = MaterialRequest(
        mr_number=mr_num,
        user_id=current_user.id,
        outlet_id=outlet_id,
        company_profile_id=company_profile_id or current_user.company_profile_id,
        category=category,
        description=description,
        status=MRStatus.submitted,
        submitted_at=datetime.now(),
    )
    db.add(mr)
    db.commit()
    db.refresh(mr)
    return {"id": mr.id, "mr_number": mr.mr_number, "status": mr.status.value}


# ── Manual Sync Retry (Admin/Manager) ─────────────────────────────────────────

@router.post("/material-requests/{mr_id}/sync-cmms")
async def api_sync_mr_cmms(
    mr_id: int,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """API: manually trigger native approval for a material request."""
    from app.services.native_operations_service import approve_material_request_natively

    if current_user.role not in (UserRole.admin, UserRole.territory_manager):
        raise HTTPException(status_code=403, detail="Admin or manager role required.")

    mr = db.query(MaterialRequest).filter(MaterialRequest.id == mr_id).first()
    if not mr:
        raise HTTPException(status_code=404, detail="Material request not found.")

    approve_material_request_natively(mr, db)
    return {"status": "synced", "cmms_ref": mr.cmms_ref}


from fastapi import File, UploadFile
import os
import shutil
from app.models.procurement import WorkOrder, WorkOrderStatus, QCStatus


@router.post("/work-orders/{wo_id}/qc-approve")
async def api_work_order_qc_approve(
    wo_id: int,
    qc_result: str = Form("passed"),
    qc_notes: Optional[str] = Form(default=None),
    qc_photo: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    if current_user.role not in [UserRole.admin, UserRole.territory_manager, UserRole.qc_manager]:
        raise HTTPException(status_code=403, detail="QC approval permission required.")

    wo = db.query(WorkOrder).filter(WorkOrder.id == wo_id).first()
    if not wo:
        raise HTTPException(status_code=404, detail="Work order not found.")

    photo_path = None
    if qc_photo and qc_photo.filename:
        file_bytes = await qc_photo.read()
        if file_bytes:
            from app.utils.s3_service import upload_image_file
            photo_path = upload_image_file(
                db=db,
                file_bytes=file_bytes,
                original_filename=qc_photo.filename,
                folder_prefix="qc_photos",
                content_type=qc_photo.content_type or "image/jpeg"
            )

    if photo_path:
        wo.qc_photo_url = photo_path

    wo.qc_notes = qc_notes
    wo.qc_verified_at = datetime.utcnow()
    wo.qc_verified_by_id = current_user.id

    from app.services.channel_partner_notification import record_material_request_history_log

    mr = wo.material_request or (wo.quotation.material_request if wo.quotation else None)

    if qc_result.lower() == "passed":
        wo.qc_status = QCStatus.passed
        wo.status = WorkOrderStatus.concluded
        if mr:
            old_st = mr.status.value
            mr.status = MRStatus.completed
            record_material_request_history_log(
                db=db,
                material_request_id=mr.id,
                action="qc_approved",
                performed_by_id=current_user.id,
                old_status=old_st,
                new_status=MRStatus.completed.value,
                vendor_id=mr.vendor_id,
                notes=f"QC Approval passed by {current_user.full_name} via Mobile App."
            )
        db.commit()
        return {"status": "success", "message": f"Work Order {wo.wo_number} QC Approved.", "qc_photo_url": photo_path}
    else:
        wo.qc_status = QCStatus.failed
        if mr:
            old_st = mr.status.value
            record_material_request_history_log(
                db=db,
                material_request_id=mr.id,
                action="qc_failed",
                performed_by_id=current_user.id,
                old_status=old_st,
                new_status=mr.status.value,
                vendor_id=mr.vendor_id,
                notes=f"QC Inspection marked Failed by {current_user.full_name} via Mobile App."
            )
        db.commit()
        return {"status": "failed", "message": f"Work Order {wo.wo_number} QC Failed."}


@router.post("/orders/{order_id}/sync-connect")
async def api_sync_order_connect(
    order_id: int,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """API: manually trigger native order confirmation."""
    from app.models.order import Order
    from app.services.native_operations_service import confirm_order_natively

    if current_user.role not in (UserRole.admin, UserRole.territory_manager):
        raise HTTPException(status_code=403, detail="Admin or manager role required.")

    order = db.query(Order).filter(Order.id == order_id).first()
    if not order:
        raise HTTPException(status_code=404, detail="Order not found.")

    confirm_order_natively(order, db)
    return {"status": "synced", "connect_ref": order.connect_ref}


class PaymentSubmissionRequest(BaseModel):
    payment_ids: List[int] = Field(..., min_length=1, description="List of payment IDs to submit")
    notes: Optional[str] = Field(None, max_length=500)


@router.post("/payment-submissions")
async def submit_payments_api(
    body: PaymentSubmissionRequest,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    payment_ids = body.payment_ids
    notes = body.notes
    if not payment_ids:
        raise HTTPException(status_code=400, detail="Select at least one payment.")

    from app.models.payment_submission import PaymentSubmission, SubmissionStatus
    from app.utils.ref_generator import submission_ref

    ref = submission_ref(db, PaymentSubmission)
    sub = PaymentSubmission(
        submission_ref=ref,
        rep_id=current_user.id,
        notes=notes or None,
        status=SubmissionStatus.pending,
    )
    db.add(sub)
    db.flush()

    total = 0
    d2000 = d500 = d200 = d100 = d50 = d20 = d10 = 0
    online_total = 0
    linked_count = 0

    for pid in payment_ids:
        payment = db.query(Payment).filter(
            Payment.id == pid,
            Payment.user_id == current_user.id,
            Payment.submission_id.is_(None)
        ).first()
        if payment:
            payment.submission_id = sub.id
            total += float(payment.amount)
            d2000 += payment.denom_2000
            d500 += payment.denom_500
            d200 += payment.denom_200
            d100 += payment.denom_100
            d50 += payment.denom_50
            d20 += payment.denom_20
            d10 += payment.denom_10
            if payment.method.value != "cash":
                online_total += float(payment.amount)
            linked_count += 1

    if linked_count == 0:
        db.rollback()
        raise HTTPException(status_code=400, detail="None of the selected payments could be submitted.")

    sub.total_amount = total
    sub.denom_2000_total = d2000
    sub.denom_500_total = d500
    sub.denom_200_total = d200
    sub.denom_100_total = d100
    sub.denom_50_total = d50
    sub.denom_20_total = d20
    sub.denom_10_total = d10
    sub.online_amount = online_total
    db.commit()
    db.refresh(sub)

    return {
        "id": sub.id,
        "submission_ref": sub.submission_ref,
        "status": sub.status.value,
        "total_amount": float(sub.total_amount),
        "payment_count": linked_count,
    }


@router.post("/asset-capitalizations")
async def create_asset_capitalization_api(
    outlet_id: int,
    item_name: str,
    item_code: Optional[str] = None,
    quantity: int = 1,
    warehouse_name: Optional[str] = None,
    deployed_by: str = "rep",
    vendor_id: Optional[int] = None,
    notes: Optional[str] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.models.asset_capitalization import AssetCapitalization, ACStatus, ACSyncStatus, DeployedByType
    from app.routers.asset_capitalizations import _ac_number, _sync_ac_to_cmms
    
    ac_num = _ac_number(db)
    ac = AssetCapitalization(
        ac_number=ac_num,
        user_id=current_user.id,
        outlet_id=outlet_id,
        company_profile_id=current_user.company_profile_id,
        item_name=item_name,
        item_code=item_code or None,
        quantity=quantity,
        warehouse_name=warehouse_name or None,
        deployed_by=DeployedByType(deployed_by),
        vendor_id=vendor_id,
        status=ACStatus.pending,
        sync_status=ACSyncStatus.pending,
        notes=notes or None,
    )
    db.add(ac)
    db.commit()
    db.refresh(ac)

    # Queue CMMS sync
    try:
        await _sync_ac_to_cmms(ac, db)
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.error("Failed to sync AC %s: %s", ac.ac_number, str(exc))

    return {
        "id": ac.id,
        "ac_number": ac.ac_number,
        "status": ac.status.value,
        "sync_status": ac.sync_status.value,
    }

