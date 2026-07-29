"""
Mobile API — Phase 3 Operations
Covers: attendance (timesheet), visits, orders, payments, expenses, material requests.
All endpoints require Bearer JWT auth.
"""
from datetime import date, datetime
from typing import List, Optional

from app.utils.timezone import ist_now, ist_today

from fastapi import APIRouter, Body, Depends, File, Form, Header, HTTPException, Query, Request, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload, selectinload

from app.dependencies import get_db, require_api_auth, require_restricted_module_api_access
from app.models.beat import Beat
from app.models.company import CompanyProfile
from app.models.expense import Expense, ExpenseCategory, ExpenseStatus
from app.models.material_request import MaterialRequest, MRStatus
from app.models.order import Order, OrderItem, OrderStatus, FlowType, SyncStatus, OrderType
from app.services.sync import sync_order_to_zap
from app.services.idempotency import idempotent
from app.services.access_control import (
    require_beat_access,
    require_material_request_access,
    require_channel_partner_access,
    require_order_access,
    require_outlet_access,
    require_user_access,
    require_visit_access,
    require_warehouse_access,
    require_work_order_access,
    scope_material_request_query,
    scope_order_query,
    scope_outlet_query,
    scope_payment_query,
    scope_work_order_query,
)
from app.models.outlet import Outlet, OutletStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.product_mapping import ProductAliasMap
from app.models.product import Product, ProductCategory
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
    today = ist_today()
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
            checkin_time=ist_now(),
            approval_status=ApprovalStatus.pending,
        )
        db.add(att)
        db.flush()
    elif not att.checkin_time:
        att.checkin_time = ist_now()
        db.flush()

    ts = Timesheet(
        user_id=current_user.id,
        attendance_id=att.id,
        work_date=today,
        checkin_time=ist_now(),
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
    today = ist_today()
    ts = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id,
        Timesheet.work_date == today,
        Timesheet.status == TimesheetStatus.open,
    ).first()
    if not ts:
        raise HTTPException(status_code=400, detail="No open timesheet found for today.")

    ts.checkout_time = ist_now()
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
        att.checkout_time = ist_now()
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
        Timesheet.work_date == ist_today(),
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


@router.get("/timesheets/my-timesheets")
async def get_my_timesheets(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    query = db.query(Timesheet).filter(
        Timesheet.user_id == current_user.id
    )
    total = query.count()
    timesheets = query.order_by(Timesheet.work_date.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [
            {
                "id": ts.id,
                "work_date": ts.work_date.isoformat(),
                "checkin_time": ts.checkin_time.isoformat() if ts.checkin_time else None,
                "checkout_time": ts.checkout_time.isoformat() if ts.checkout_time else None,
                "hours_worked": ts.hours_worked or 0.0,
                "visit_count": ts.visit_count,
                "status": ts.status.value,
                "approval_status": ts.approval_status.value,
                "notes": ts.notes,
            }
            for ts in timesheets
        ]
    }


# ── Visit Records ──────────────────────────────────────────────────────────────

@router.post("/visits")
@idempotent("visit.create")
async def log_visit(
    outlet_id: int,
    gps_lat: float,
    gps_lng: float,
    purpose: Optional[str] = None,
    notes: Optional[str] = None,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    if not (-90 <= gps_lat <= 90 and -180 <= gps_lng <= 180):
        raise HTTPException(status_code=400, detail="Invalid GPS coordinates.")
    outlet = require_outlet_access(db, current_user, outlet_id, active_only=True)

    distance = None
    if outlet.gps_lat and outlet.gps_lng:
        distance = haversine_distance(gps_lat, gps_lng, outlet.gps_lat, outlet.gps_lng)
    from app.models.company import SystemConfiguration
    config = db.query(SystemConfiguration).filter(
        SystemConfiguration.id == 1
    ).first()
    threshold = (config.gps_threshold_metres if config else None) or 100
    visit_type = (
        "in_location"
        if distance is not None and distance <= threshold
        else "out_of_range"
    )

    today = ist_today()
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
        visit_type=visit_type,
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
    notes: Optional[str] = None,
    no_order_reason: Optional[str] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    visit = require_visit_access(db, current_user, visit_id)
    if visit.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Visit record not found.")

    if visit.checkout_time:
        raise HTTPException(status_code=400, detail="Visit already checked out.")

    linked_order = db.query(Order.id).filter(Order.visit_id == visit.id).first()
    if not visit.order_id and not linked_order and not (no_order_reason or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A no-order reason is required when the visit has no order.",
        )

    visit.checkout_time = datetime.now()
    if notes:
        visit.notes = notes
    if no_order_reason:
        visit.no_order_reason = no_order_reason
    db.flush()

    from app.services.timesheet_service import sync_auto_timesheet_line_item
    sync_auto_timesheet_line_item(db, visit)

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

def resolve_l3_warehouse_for_order(user: User, outlet_id: Optional[int], beat_id: Optional[int], db: Session) -> Optional[int]:
    """
    Resolves warehouse from L3 Position hierarchy:
    Outlet -> Beat -> L1 Position -> L2 Position -> L3 Position -> L3 User -> geography -> warehouse.
    """
    from app.models.position import Position, PositionLevel
    from app.models.beat import Beat

    positions_to_check = []
    if beat_id:
        beat = require_beat_access(db, user, beat_id, active_only=True)
        cross_role_resolution = getattr(user.role, "value", str(user.role)) in {
            UserRole.admin.value, UserRole.qc_manager.value,
            UserRole.vendor_admin.value, UserRole.vendor_technician.value,
        }
        positions_to_check = [
            pos for pos in beat.positions
            if pos.is_active and getattr(pos.level, "value", str(pos.level)) == "L1"
            and (cross_role_resolution or user in pos.users or not pos.users)
        ]
    if not positions_to_check:
        positions_to_check = [
            pos for pos in (list(user.positions) if user and getattr(user, "positions", None) else [])
            if pos.is_active
        ]

    for pos in positions_to_check:
        curr = pos
        l3_pos = None
        visited = set()
        while curr and curr.id not in visited:
            visited.add(curr.id)
            if curr.level == PositionLevel.L3 or getattr(curr.level, "value", str(curr.level)) == "L3":
                l3_pos = curr
                break
            curr = curr.reporting_to

        # Required rule: L3 Position -> assigned L3 User -> Geography -> active Warehouse.
        if l3_pos:
            for l3_user in l3_pos.users:
                if l3_user.is_active and l3_user.geography:
                    wh = next((w for w in l3_user.geography.warehouses if w.is_active), None)
                    if wh:
                        return wh.id
            if l3_pos.reporting_to and l3_pos.reporting_to.level == PositionLevel.L4:
                for l4_user in l3_pos.reporting_to.users:
                    if l4_user.is_active and l4_user.geography:
                        wh = next((w for w in l4_user.geography.warehouses if w.is_active), None)
                        if wh:
                            return wh.id

        wh = l3_pos.resolve_warehouse(db) if l3_pos else pos.resolve_warehouse(db)
        if wh:
            return wh.id

    # Fallback to user allowed warehouses
    from app.utils.geography_scope import get_user_allowed_warehouse_ids
    allowed_whs = get_user_allowed_warehouse_ids(user, db)
    if allowed_whs and len(allowed_whs) > 0:
        return allowed_whs[0]
    return None


def _descendant_position_ids(user: User, db: Session, level: Optional[str] = None) -> set[int]:
    """Return active positions below the authenticated user's reporting tree."""
    from app.models.position import Position

    role_val = getattr(user.role, "value", str(user.role or ""))
    if role_val == UserRole.admin.value:
        query = db.query(Position).filter(Position.is_active == True)
        if level:
            query = query.filter(Position.level == level)
        return {p.id for p in query.all()}

    roots = [p for p in user.positions if p.is_active]
    seen = {p.id for p in roots}
    frontier = list(roots)
    descendants: set[int] = set()
    while frontier:
        parent = frontier.pop()
        for child in parent.direct_reports:
            if child.is_active and child.id not in seen:
                seen.add(child.id)
                descendants.add(child.id)
                frontier.append(child)
    if level:
        descendants = {
            p.id for p in db.query(Position).filter(Position.id.in_(descendants)).all()
            if getattr(p.level, "value", str(p.level)) == level
        }
    return descendants


def _allowed_l1_users(user: User, db: Session) -> list[User]:
    from app.models.position import Position

    position_ids = _descendant_position_ids(user, db, "L1")
    if not position_ids:
        return []
    return (
        db.query(User)
        .join(User.positions)
        .filter(
            Position.id.in_(position_ids),
            User.is_active == True,
            User.role == UserRole.field_rep,
        )
        .distinct()
        .order_by(User.full_name)
        .all()
    )


@router.get("/orders/warehouse-context")
async def get_order_warehouse_context(
    outlet_id: Optional[int] = None,
    beat_id: Optional[int] = None,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    warehouse_id = resolve_l3_warehouse_for_order(current_user, outlet_id, beat_id, db)
    if not warehouse_id:
        raise HTTPException(status_code=404, detail="No active warehouse is mapped through the L3 reporting hierarchy.")
    from app.models.warehouse import Warehouse
    warehouse = require_warehouse_access(
        db, current_user, warehouse_id
    )
    return {
        "warehouse_id": warehouse.id,
        "warehouse_name": warehouse.name,
        "warehouse_code": warehouse.code,
        "warehouse_address": warehouse.address,
    }


@router.get("/orders/outlet-today-l1-orders")
async def get_outlet_today_l1_orders(
    outlet_id: int,
    beat_id: Optional[int] = Query(default=None),
    subordinate_user_id: Optional[int] = Query(default=None),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.utils.timezone import ist_today

    require_outlet_access(db, current_user, outlet_id, active_only=True)
    if beat_id:
        require_beat_access(db, current_user, beat_id, active_only=True)

    query = db.query(Order).options(
        joinedload(Order.user), selectinload(Order.items)
    ).filter(
        Order.outlet_id == outlet_id,
        Order.order_date == ist_today(),
    )

    if beat_id:
        query = query.filter(Order.beat_id == beat_id)

    if subordinate_user_id:
        allowed_ids = {u.id for u in _allowed_l1_users(current_user, db)}
        if subordinate_user_id not in allowed_ids:
            raise HTTPException(status_code=403, detail="Selected L1 user is outside your reporting hierarchy.")
        query = query.filter(Order.user_id == subordinate_user_id)
    else:
        sub_ids = [u.id for u in _allowed_l1_users(current_user, db)]
        query = query.filter(Order.user_id.in_(sub_ids or [-1]))

    total = query.count()
    orders = query.order_by(Order.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    items_res = []
    for o in orders:
        items_res.append({
            "id": o.id,
            "order_number": o.order_number,
            "order_type": o.order_type.value if hasattr(o.order_type, "value") else str(o.order_type),
            "user_id": o.user_id,
            "user_name": o.user.full_name if o.user else "Unknown Rep",
            "status": o.status.value if hasattr(o.status, "value") else str(o.status),
            "total_amount": o.total_amount,
            "created_at": o.created_at.isoformat() if o.created_at else None,
            "is_company_order": o.is_company_order,
            "is_paid": o.is_paid,
            "payment_type": o.payment_type,
            "payment_mode": o.payment_mode,
            "payment_reference": o.payment_reference,
        })

    return {
        "page": page, "per_page": per_page, "total": total,
        "orders": items_res,
    }


@router.post("/orders")
@idempotent("order.create")
async def create_order(
    items: list[dict],  # [{product_id, quantity, unit_price, gst_rate, discount_pct}]
    order_type: str = "Secondary",
    outlet_id: Optional[int] = None,
    channel_partner_id: Optional[int] = None,
    party_id: Optional[int] = None,
    party_type: Optional[str] = None,  # "Outlet", "Channel Partner"
    warehouse_id: Optional[int] = None,
    is_company_order: bool = False,
    is_paid: bool = False,
    payment_type: Optional[str] = None,  # Full, Partial, Credit
    payment_mode: Optional[str] = None,  # Cash, UPI, NEFT/RTGS, Others
    payment_reference: Optional[str] = None,
    delivery_address: Optional[str] = None,
    is_regional_company: bool = False,
    visit_id: Optional[int] = None,
    beat_id: Optional[int] = None,
    notes: Optional[str] = None,
    amount_collected: Optional[float] = 0.0,
    payment_method: Optional[str] = "cash",
    transaction_ref: Optional[str] = None,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.models.order import OrderType, PaymentSettlementStatus
    from app.models.payment import Payment, PaymentMethod, PaymentStatus
    from app.models.timesheet import VisitRecord
    from app.utils.ref_generator import payment_ref
    from app.utils.timezone import ist_today, ist_now
    from decimal import Decimal

    if not items:
        raise HTTPException(status_code=400, detail="Order must have at least one item.")

    try:
        ot = OrderType(order_type)
    except ValueError:
        ot = OrderType.secondary

    # Party Unification Logic
    resolved_party_type = party_type or ("Channel Partner" if ot == OrderType.primary else "Outlet")
    if resolved_party_type not in ("Outlet", "Channel Partner"):
        raise HTTPException(status_code=400, detail="party_type must be 'Outlet' or 'Channel Partner'.")
    resolved_party_id = party_id

    if resolved_party_type == "Outlet":
        target_outlet_id = resolved_party_id or outlet_id
        target_cp_id = channel_partner_id
    else:
        target_cp_id = resolved_party_id or channel_partner_id
        target_outlet_id = None

    target_visit_id = None

    if ot == OrderType.primary or resolved_party_type == "Channel Partner":
        if current_user.role == UserRole.field_rep:
            raise HTTPException(status_code=403, detail="Primary Orders are restricted to TMs and Admins (L2/L3/L4).")
        if not target_cp_id:
            raise HTTPException(status_code=400, detail="Primary Orders must be placed directly against a valid Channel Partner.")
        require_channel_partner_access(db, current_user, int(target_cp_id))
        resolved_party_type = "Channel Partner"
        resolved_party_id = target_cp_id
        is_company_order = True
    else:
        # Secondary Order
        if not target_outlet_id:
            raise HTTPException(status_code=400, detail="Outlet ID is required for Secondary Orders.")
        outlet = require_outlet_access(
            db, current_user, int(target_outlet_id), active_only=True
        )
        resolved_party_type = "Outlet"
        resolved_party_id = target_outlet_id

        # Mandatory Visit Record Check
        visit = None
        if visit_id:
            visit = db.query(VisitRecord).filter(VisitRecord.id == visit_id, VisitRecord.user_id == current_user.id).first()
        if not visit:
            visit = db.query(VisitRecord).filter(
                VisitRecord.user_id == current_user.id,
                VisitRecord.outlet_id == target_outlet_id,
                func.date(VisitRecord.visit_time) == ist_today()
            ).order_by(VisitRecord.visit_time.desc()).first()

        if not visit:
            raise HTTPException(status_code=400, detail="A mandatory Visit record against the outlet is required for Secondary Orders.")

        target_visit_id = visit.id

    # Resolve Warehouse if not provided
    resolved_wh_id = warehouse_id
    if not resolved_wh_id:
        resolved_wh_id = resolve_l3_warehouse_for_order(current_user, target_outlet_id, beat_id, db)
    if not resolved_wh_id:
        raise HTTPException(status_code=400, detail="No active warehouse could be resolved from the L3 reporting hierarchy.")

    # Process Payment Flag Defaults
    if is_company_order:
        if payment_type not in ("Credit", "Full", "Partial"):
            raise HTTPException(status_code=400, detail="Company Orders require payment_type Credit, Full, or Partial.")
        if payment_type == "Credit":
            is_paid = False
            payment_mode = None
            payment_reference = None
        elif payment_type in ("Full", "Partial"):
            is_paid = True
            if payment_mode not in ("Cash", "UPI", "NEFT/RTGS", "Others"):
                raise HTTPException(status_code=400, detail="Paid Company Orders require a valid payment_mode.")
            if payment_mode != "Cash" and not (payment_reference or "").strip():
                raise HTTPException(status_code=400, detail="A payment reference is required for non-cash Paid Orders.")
    else:
        is_paid = False
        payment_type = None
        payment_mode = None
        payment_reference = None

    product_ids = [int(it.get("product_id", 0)) for it in items]
    if len(product_ids) != len(set(product_ids)):
        raise HTTPException(
            status_code=400,
            detail="An order cannot contain the same product more than once.",
        )
    products = db.query(Product).filter(Product.id.in_(product_ids), Product.is_active == True).all()
    products_by_id = {p.id: p for p in products}
    if len(products_by_id) != len(set(product_ids)):
        raise HTTPException(status_code=400, detail="One or more selected products are invalid or inactive.")
    if any(p.category_type.value != "Sales" for p in products):
        raise HTTPException(status_code=400, detail="Orders may contain only products with Category Scope Sales.")
    if is_company_order:
        from app.models.product_warehouse import ProductWarehouseStock
        unavailable = []
        for product in products:
            if not product.is_stockable:
                unavailable.append(product.name)
                continue
            stock = db.query(ProductWarehouseStock).filter(
                ProductWarehouseStock.product_id == product.id,
                ProductWarehouseStock.warehouse_id == resolved_wh_id,
                ProductWarehouseStock.is_active == True,
            ).first()
            fallback_qty = product.stock_qty if product.warehouse_id == resolved_wh_id else 0
            requested_qty = next(int(it.get("quantity", 0)) for it in items if int(it["product_id"]) == product.id)
            if (stock.stock_qty if stock else fallback_qty) < requested_qty:
                unavailable.append(product.name)
        if unavailable:
            raise HTTPException(
                status_code=400,
                detail=f"Company Order unavailable from the resolved warehouse: {', '.join(unavailable)}.",
            )

    ord_num = order_number(db, Order)
    o = Order(
        order_number=ord_num,
        outlet_id=target_outlet_id,
        party_id=resolved_party_id,
        party_type=resolved_party_type,
        user_id=current_user.id,
        beat_id=beat_id,
        channel_partner_id=target_cp_id,
        warehouse_id=resolved_wh_id,
        is_company_order=is_company_order,
        is_paid=is_paid,
        payment_type=payment_type,
        payment_mode=payment_mode,
        payment_reference=payment_reference,
        delivery_address=(delivery_address or "").strip() or None,
        is_regional_company=is_regional_company,
        visit_id=target_visit_id,
        order_type=ot,
        company_profile_id=current_user.company_profile_id,
        status=OrderStatus.draft,
        notes=notes,
    )
    db.add(o)
    db.flush()
    if target_visit_id:
        visit.order_id = o.id

    for it in items:
        db.add(OrderItem(
            order_id=o.id,
            product_id=it["product_id"],
            quantity=it.get("quantity", 1),
            unit_price=it["unit_price"],
            gst_rate=it.get("gst_rate", 0),
            discount_pct=it.get("discount_pct", 0),
        ))
    db.flush()
    db.refresh(o)

    # Process Payments Flow
    if (ot == OrderType.secondary and is_regional_company) or (is_company_order and is_paid):
        amt_col = float(amount_collected) if amount_collected else 0.0
        if amt_col > 0:
            pay_ref_str = payment_ref(db, Payment)
            pm = PaymentMethod(payment_method) if payment_method in [m.value for m in PaymentMethod] else PaymentMethod.cash
            pay = Payment(
                payment_ref=pay_ref_str,
                order_id=o.id,
                outlet_id=o.outlet_id,
                user_id=current_user.id,
                amount=Decimal(str(amt_col)),
                method=pm,
                transaction_ref=payment_reference or transaction_ref or None,
                status=PaymentStatus.collected,
                collected_at=ist_now(),
            )
            db.add(pay)
            db.flush()

        order_total_val = float(o.total_amount)
        if amt_col >= order_total_val and order_total_val > 0:
            o.payment_settlement = PaymentSettlementStatus.paid
        elif amt_col > 0:
            o.payment_settlement = PaymentSettlementStatus.partial
        else:
            o.payment_settlement = PaymentSettlementStatus.unpaid

    db.commit()
    db.refresh(o)
    return {
        "id": o.id,
        "order_number": o.order_number,
        "party_id": o.party_id,
        "party_type": o.party_type,
        "warehouse_id": o.warehouse_id,
        "order_type": o.order_type.value,
        "status": o.status.value,
        "total_amount": o.total_amount,
        "is_company_order": o.is_company_order,
        "is_paid": o.is_paid,
        "payment_type": o.payment_type,
        "payment_mode": o.payment_mode,
        "payment_reference": o.payment_reference,
        "delivery_address": o.delivery_address,
        "party_name": o.party_name,
        "warehouse_name": o.warehouse.name if o.warehouse else None,
        "payment_settlement": o.payment_settlement.value,
        "item_count": o.item_count,
    }


@router.patch("/orders/{order_id}/submit")
async def submit_order(
    order_id: int,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    o = require_order_access(db, current_user, order_id)
    if o.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Order not found.")
    if o.status != OrderStatus.draft:
        raise HTTPException(status_code=400, detail=f"Cannot submit order in '{o.status.value}' state.")
    o.status = OrderStatus.submitted
    o.sync_status = SyncStatus.pending
    db.commit()

    await sync_order_to_zap(o, db)

    return {"id": o.id, "order_number": o.order_number, "status": o.status.value}


@router.get("/orders/my")
async def my_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    query = db.query(Order).options(
        joinedload(Order.outlet), selectinload(Order.items)
    ).filter(
        Order.user_id == current_user.id
    ).order_by(Order.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total, "page": page, "per_page": per_page,
        "items": [
            {
                "id": o.id, "order_number": o.order_number, "status": o.status.value,
                "party_id": o.party_id, "party_type": o.party_type, "party_name": o.party_name,
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
    o = require_order_access(db, current_user, order_id)
    return {
        "id": o.id,
        "order_number": o.order_number,
        "status": o.status.value,
        "party_id": o.party_id,
        "party_type": o.party_type,
        "party_name": o.party_name,
        "outlet_name": o.outlet.name if o.outlet else None,
        "warehouse_id": o.warehouse_id,
        "warehouse_name": o.warehouse.name if o.warehouse else None,
        "is_company_order": o.is_company_order,
        "is_paid": o.is_paid,
        "payment_type": o.payment_type,
        "payment_mode": o.payment_mode,
        "payment_reference": o.payment_reference,
        "delivery_address": o.delivery_address,
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
@idempotent("payment.create")
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
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    try:
        pay_method = PaymentMethod(method)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid payment method '{method}'.")

    outlet = require_outlet_access(db, current_user, outlet_id, active_only=True)
    order = None
    if order_id is not None:
        order = require_order_access(db, current_user, order_id)
        if order.outlet_id != outlet.id:
            raise HTTPException(
                status_code=400,
                detail="The selected order does not belong to the selected outlet.",
            )

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


@router.get("/expenses/my-expenses")
async def get_my_expenses(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    query = db.query(Expense).filter(
        Expense.user_id == current_user.id
    )
    total = query.count()
    expenses = query.order_by(Expense.expense_date.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [
            {
                "id": exp.id,
                "category": exp.category.value if exp.category else "misc",
                "amount": float(exp.amount),
                "description": exp.description,
                "status": exp.status.value,
                "expense_date": exp.expense_date.isoformat(),
            }
            for exp in expenses
        ]
    }


@router.post("/expenses/{expense_id}/receipt")
async def upload_receipt_api(
    expense_id: int,
    request: Request,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Mobile API: upload receipt image for an expense."""
    import os

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

    from app.utils.s3_service import upload_image_file
    expense.receipt_url = upload_image_file(
        db,
        contents,
        file.filename,
        folder_prefix="receipts",
        content_type=getattr(file, "content_type", None) or "application/octet-stream",
        bucket_type="files",
    )
    db.commit()
    return {"receipt_url": expense.receipt_url}


# ── Material Requests ──────────────────────────────────────────────────────────

def _outlet_payload(outlet: Outlet) -> dict:
    return {
        "id": outlet.id, "name": outlet.name, "code": outlet.code,
        "address": outlet.address, "contact": outlet.mobile,
        "owner_name": outlet.owner_name, "gps_lat": outlet.gps_lat,
        "gps_lng": outlet.gps_lng, "photo_url": outlet.photo_url,
    }


def _product_payload(product: Product, available_quantity: Optional[int] = None) -> dict:
    return {
        "id": product.id, "name": product.name, "sku": product.sku,
        "category_scope": product.category_type.value,
        "available_quantity": available_quantity,
    }


async def _store_required_image(db: Session, upload: UploadFile, prefix: str) -> str:
    allowed = {"image/jpeg", "image/png", "image/webp"}
    if upload.content_type not in allowed:
        raise HTTPException(status_code=400, detail=f"{prefix.replace('_', ' ').title()} must be JPG, PNG, or WEBP.")
    contents = await upload.read()
    if not contents:
        raise HTTPException(status_code=400, detail=f"{prefix.replace('_', ' ').title()} is empty.")
    if len(contents) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail=f"{prefix.replace('_', ' ').title()} exceeds 5 MB.")
    from app.utils.s3_service import upload_image_file
    return upload_image_file(
        db=db, file_bytes=contents, original_filename=upload.filename or f"{prefix}.jpg",
        folder_prefix=f"material_requests/{prefix}", content_type=upload.content_type,
    )


@router.get("/outlets/{outlet_id}/material-request-context")
async def material_request_context(
    outlet_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    outlet = require_outlet_access(db, current_user, outlet_id, active_only=True)
    query = db.query(Product).filter(
        Product.is_active == True,
        Product.category_type == ProductCategory.marketing_procurement,
    )
    total = query.count()
    products = query.order_by(Product.name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "outlet": _outlet_payload(outlet),
        "page": page, "per_page": per_page, "total": total,
        "products": [_product_payload(p) for p in products],
    }


@router.post("/material-requests")
@idempotent("material_request.create")
async def submit_material_request(
    outlet_id: int = Form(...),
    product_id: int = Form(...),
    description: str = Form(...),
    dimension_length: Optional[float] = Form(default=None),
    dimension_width: Optional[float] = Form(default=None),
    dimension_height: Optional[float] = Form(default=None),
    dimension_depth: Optional[float] = Form(default=None),
    dimension_unit: str = Form(default="cm"),
    present_outlet_image: UploadFile = File(...),
    installation_place_image: UploadFile = File(...),
    customer_approval_letter_image: UploadFile = File(...),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    outlet = require_outlet_access(db, current_user, outlet_id, active_only=True)
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True,
        Product.category_type == ProductCategory.marketing_procurement,
    ).first()
    if not product:
        raise HTTPException(status_code=400, detail="Select one active Marketing - Procurement product.")
    description = description.strip()
    if len(description) < 5:
        raise HTTPException(status_code=400, detail="Request description must contain at least 5 characters.")
    dimensions = [dimension_length, dimension_width, dimension_height, dimension_depth]
    if any(value is not None and value <= 0 for value in dimensions):
        raise HTTPException(status_code=400, detail="Every supplied dimension must be greater than zero.")
    if dimension_unit not in {"cm", "mm", "m", "ft", "in"}:
        raise HTTPException(status_code=400, detail="Unsupported dimension unit.")

    present_url = await _store_required_image(db, present_outlet_image, "present_outlet")
    installation_url = await _store_required_image(db, installation_place_image, "installation_place")
    approval_url = await _store_required_image(db, customer_approval_letter_image, "customer_approval_letter")
    mr_num = mr_number(db, MaterialRequest)
    dimension_text = " x ".join(str(v) if v is not None else "—" for v in dimensions) + f" {dimension_unit}" if any(v is not None for v in dimensions) else None
    mr = MaterialRequest(
        mr_number=mr_num,
        user_id=current_user.id,
        outlet_id=outlet_id,
        product_id=product.id,
        company_profile_id=current_user.company_profile_id,
        category=product.category_type.value,
        description=description,
        approx_dimensions=dimension_text,
        dimension_length=dimension_length, dimension_width=dimension_width,
        dimension_height=dimension_height, dimension_depth=dimension_depth,
        dimension_unit=dimension_unit,
        image_url=present_url, present_outlet_image_url=present_url,
        installation_place_image_url=installation_url,
        customer_approval_letter_image_url=approval_url,
        outlet_name_snapshot=outlet.name, outlet_address_snapshot=outlet.address,
        outlet_contact_snapshot=outlet.mobile, outlet_latitude_snapshot=outlet.gps_lat,
        outlet_longitude_snapshot=outlet.gps_lng,
        status=MRStatus.submitted,
        submitted_at=ist_now(),
    )
    db.add(mr)
    db.commit()
    db.refresh(mr)
    return {"id": mr.id, "mr_number": mr.mr_number, "status": mr.status.value}


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

    wo = require_work_order_access(db, current_user, wo_id)
    normalized_result = qc_result.strip().lower()
    if normalized_result not in {"passed", "failed"}:
        raise HTTPException(status_code=400, detail="QC result must be passed or failed.")
    if wo.status != WorkOrderStatus.qc_pending or wo.qc_status != QCStatus.pending:
        raise HTTPException(status_code=409, detail="Work Order is not awaiting QC review.")

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

    if normalized_result == "passed":
        wo.qc_status = QCStatus.passed
        wo.status = WorkOrderStatus.completed
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


@router.get("/outlets/{outlet_id}/asset-products")
async def outlet_asset_products(
    outlet_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.models.product_warehouse import ProductWarehouseStock
    from app.models.warehouse import Warehouse
    outlet = require_outlet_access(db, current_user, outlet_id, active_only=True)
    warehouse_id = resolve_l3_warehouse_for_order(current_user, outlet_id, outlet.beat_id, db)
    warehouse = require_warehouse_access(db, current_user, warehouse_id)
    query = (
        db.query(Product, ProductWarehouseStock)
        .join(ProductWarehouseStock, ProductWarehouseStock.product_id == Product.id)
        .filter(
            Product.is_active == True,
            Product.category_type == ProductCategory.marketing_stock,
            ProductWarehouseStock.warehouse_id == warehouse.id,
            ProductWarehouseStock.is_active == True,
            ProductWarehouseStock.stock_qty > 0,
        )
    )
    total = query.count()
    rows = query.order_by(Product.name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "outlet": _outlet_payload(outlet),
        "warehouse": {"id": warehouse.id, "name": warehouse.name, "code": warehouse.code},
        "page": page, "per_page": per_page, "total": total,
        "products": [_product_payload(product, stock.stock_qty) for product, stock in rows],
    }


@router.get("/outlets/{outlet_id}/assets")
async def outlet_assets(
    outlet_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.models.asset_capitalization import AssetCapitalization
    outlet = require_outlet_access(db, current_user, outlet_id, active_only=True)
    query = db.query(AssetCapitalization).filter(
        AssetCapitalization.outlet_id == outlet_id,
    )
    total = query.count()
    assets = query.order_by(AssetCapitalization.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {"page": page, "per_page": per_page, "total": total, "items": [{
        "id": item.id, "ac_number": item.ac_number, "item_name": item.item_name,
        "item_code": item.item_code, "quantity": item.quantity,
        "warehouse_name": item.warehouse_name, "status": item.status.value,
        "image_url": item.image_url,
        "deployed_at": item.deployed_at.isoformat() if item.deployed_at else None,
    } for item in assets]}


@router.post("/asset-capitalizations")
@idempotent("asset.create")
async def create_asset_capitalization_api(
    outlet_id: int = Form(...),
    product_id: int = Form(...),
    quantity: int = Form(default=1),
    notes: Optional[str] = Form(default=None),
    image: Optional[UploadFile] = File(default=None),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    from app.models.asset_capitalization import AssetCapitalization, ACStatus, ACSyncStatus, DeployedByType
    from app.models.inventory import StockMovement
    from app.models.product_warehouse import ProductWarehouseStock
    from app.models.warehouse import Warehouse
    from app.routers.asset_capitalizations import _ac_number
    if quantity <= 0:
        raise HTTPException(status_code=400, detail="Quantity must be at least one.")
    outlet = require_outlet_access(db, current_user, outlet_id, active_only=True)
    warehouse_id = resolve_l3_warehouse_for_order(current_user, outlet_id, outlet.beat_id, db)
    warehouse = require_warehouse_access(db, current_user, warehouse_id)
    product = db.query(Product).filter(
        Product.id == product_id, Product.is_active == True,
        Product.category_type == ProductCategory.marketing_stock,
    ).first()
    if not warehouse or not product:
        raise HTTPException(status_code=400, detail="Product or resolved L3 warehouse is invalid.")
    stock = db.query(ProductWarehouseStock).filter(
        ProductWarehouseStock.product_id == product.id,
        ProductWarehouseStock.warehouse_id == warehouse.id,
        ProductWarehouseStock.is_active == True,
    ).with_for_update().first()
    if not stock or stock.stock_qty < quantity:
        available = stock.stock_qty if stock else 0
        raise HTTPException(status_code=409, detail=f"Only {available} unit(s) are available in {warehouse.name}.")

    image_url = None
    if image and image.filename:
        image_url = await _store_required_image(db, image, "asset_deployment")
    ac_num = _ac_number(db)
    ac = AssetCapitalization(
        ac_number=ac_num,
        user_id=current_user.id,
        outlet_id=outlet_id,
        product_id=product.id,
        warehouse_id=warehouse.id,
        company_profile_id=current_user.company_profile_id,
        item_name=product.name,
        item_code=product.sku,
        quantity=quantity,
        warehouse_name=warehouse.name,
        deployed_by=DeployedByType.rep,
        status=ACStatus.deployed,
        sync_status=ACSyncStatus.not_applicable,
        notes=notes or None,
        image_url=image_url,
        deployed_at=ist_now(),
    )
    db.add(ac)
    stock.stock_qty -= quantity
    db.add(StockMovement(
        product_id=product.id, warehouse_id=warehouse.id, movement_type="OUTWARD",
        quantity=quantity, reference_no=ac_num,
        notes=f"Marketing asset deployed to outlet {outlet.name}",
        created_by_id=current_user.id,
    ))
    try:
        db.commit()
        db.refresh(ac)
    except Exception:
        db.rollback()
        raise

    return {
        "id": ac.id,
        "ac_number": ac.ac_number,
        "status": ac.status.value,
        "sync_status": ac.sync_status.value,
    }


# ── Mobile History & List Endpoints ──────────────────────────────────────────

@router.get("/attendance/history")
async def attendance_history(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List authenticated user's past attendance & timesheet history."""
    query = db.query(Timesheet).filter(Timesheet.user_id == current_user.id).order_by(Timesheet.work_date.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": ts.id,
                "work_date": ts.work_date.isoformat(),
                "checkin_time": ts.checkin_time.isoformat() if ts.checkin_time else None,
                "checkout_time": ts.checkout_time.isoformat() if ts.checkout_time else None,
                "hours_worked": ts.hours_worked,
                "visit_count": ts.visit_count,
                "status": ts.status.value,
            }
            for ts in items
        ],
    }


@router.get("/visits/my")
async def my_visits(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    target_date: Optional[str] = Query(default=None),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List authenticated user's visit records."""
    query = db.query(VisitRecord).filter(VisitRecord.user_id == current_user.id)
    if target_date:
        try:
            d = date.fromisoformat(target_date)
            query = query.filter(func.date(VisitRecord.visit_time) == d)
        except ValueError:
            pass
    query = query.order_by(VisitRecord.visit_time.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": v.id,
                "outlet_id": v.outlet_id,
                "outlet_name": v.outlet.name if v.outlet else None,
                "visit_time": v.visit_time.isoformat() if v.visit_time else None,
                "checkout_time": v.checkout_time.isoformat() if v.checkout_time else None,
                "duration_minutes": v.duration_minutes,
                "purpose": v.purpose,
                "notes": v.notes,
                "distance_from_outlet": v.distance_from_outlet,
            }
            for v in items
        ],
    }


@router.get("/payments/my")
async def my_payments(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List payments collected by authenticated user."""
    query = db.query(Payment).filter(Payment.user_id == current_user.id).order_by(Payment.collected_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": p.id,
                "payment_ref": p.payment_ref,
                "outlet_id": p.outlet_id,
                "outlet_name": p.outlet.name if p.outlet else None,
                "amount": float(p.amount),
                "method": p.method.value,
                "payment_type": p.payment_type.value,
                "status": p.status.value,
                "collected_at": p.collected_at.isoformat() if p.collected_at else None,
            }
            for p in items
        ],
    }


@router.get("/expenses/my")
async def my_expenses(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_restricted_module_api_access),
    db: Session = Depends(get_db),
):
    """List expenses submitted by authenticated user."""
    query = db.query(Expense).filter(Expense.user_id == current_user.id).order_by(Expense.expense_date.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": e.id,
                "category": e.category.value,
                "amount": float(e.amount),
                "description": e.description,
                "expense_date": e.expense_date.isoformat() if e.expense_date else None,
                "status": e.status.value,
                "receipt_url": e.receipt_url,
            }
            for e in items
        ],
    }


@router.get("/material-requests/my")
async def my_material_requests(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List material requests submitted by authenticated user."""
    query = db.query(MaterialRequest).filter(MaterialRequest.user_id == current_user.id).order_by(MaterialRequest.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": mr.id,
                "mr_number": mr.mr_number,
                "outlet_id": mr.outlet_id,
                "outlet_name": mr.outlet.name if mr.outlet else None,
                "category": mr.category,
                "description": mr.description,
                "status": mr.status.value,
                "submitted_at": mr.submitted_at.isoformat() if mr.submitted_at else None,
            }
            for mr in items
        ],
    }


@router.get("/work-orders/pending-qc")
async def pending_qc_work_orders(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List pending work orders for mobile QC inspection."""
    from app.models.procurement import WorkOrder, QCStatus
    if current_user.role not in [UserRole.admin, UserRole.territory_manager, UserRole.qc_manager]:
        raise HTTPException(status_code=403, detail="QC inspection role required.")

    query = scope_work_order_query(
        db.query(WorkOrder), current_user, db
    ).filter(
        WorkOrder.qc_status == QCStatus.pending
    ).order_by(WorkOrder.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * per_page).limit(per_page).all()
    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "items": [
            {
                "id": wo.id,
                "wo_number": wo.wo_number,
                "title": wo.title,
                "description": wo.description,
                "vendor_id": wo.vendor_id,
                "vendor_name": wo.vendor.name if wo.vendor else None,
                "amount": float(wo.amount) if wo.amount else 0,
                "status": wo.status.value,
                "qc_status": wo.qc_status.value,
                "created_at": wo.created_at.isoformat() if wo.created_at else None,
            }
            for wo in items
        ],
    }


# ── Joint Working & Analytics (EIS / MIS) ──────────────────────────────────────

@router.get("/subordinates")
async def get_subordinates(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List subordinate sales field reps in user's position hierarchy."""
    if current_user.level not in ("L2", "L3", "L4"):
        return {"items": []}
    users = _allowed_l1_users(current_user, db)

    return {
        "items": [
            {
                "id": u.id,
                "full_name": u.full_name,
                "username": u.username,
                "email": u.email,
                "role": u.role.value,
                "positions": [
                    {"id": p.id, "name": p.name, "code": p.code, "level": p.level_code}
                    for p in u.positions if p.is_active and p.level_code == "L1"
                ],
            }
            for u in users
        ]
    }


@router.get("/subordinates/{user_id}/beats")
async def get_subordinate_beats(
    user_id: int,
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=200),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """List beats assigned to a subordinate user."""
    sub_user = require_user_access(db, current_user, user_id)
    if user_id not in {u.id for u in _allowed_l1_users(current_user, db)}:
        raise HTTPException(status_code=404, detail="Subordinate user not found.")

    beat_ids = set()
    for pos in getattr(sub_user, "positions", []):
        if getattr(pos, "is_active", True):
            for b in getattr(pos, "beats", []):
                if getattr(b, "is_active", True):
                    beat_ids.add(b.id)

    if beat_ids:
        query = db.query(Beat).filter(
            Beat.id.in_(beat_ids), Beat.is_active == True
        )
        total = query.count()
        beats = query.order_by(Beat.name).offset(
            (page - 1) * per_page
        ).limit(per_page).all()
    else:
        beats = []
        total = 0

    return {
        "page": page, "per_page": per_page, "total": total,
        "items": [
            {
                "id": b.id,
                "name": b.name,
                "code": b.code,
                "beat_type": b.beat_type.value,
                "beat_grade": b.beat_grade.value if b.beat_grade else None,
                "territory_id": b.territory_id,
            }
            for b in beats
        ]
    }


@router.post("/visits/joint")
async def create_joint_visit(
    subordinate_user_id: int = Form(...),
    outlet_id: int = Form(...),
    notes: Optional[str] = Form(default=None),
    no_order_reason: Optional[str] = Form(default=None),
    linked_order_id: Optional[int] = Form(default=None),
    gps_lat: float = Form(...),
    gps_lng: float = Form(...),
    image: Optional[UploadFile] = File(default=None),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Log a hierarchy-scoped Joint Working visit and persist all outcomes."""
    if not (-90 <= gps_lat <= 90 and -180 <= gps_lng <= 180):
        raise HTTPException(status_code=400, detail="Invalid GPS coordinates.")
    if current_user.level not in ("L2", "L3", "L4"):
        raise HTTPException(status_code=403, detail="Joint Working requires an L2, L3, or L4 manager.")
    allowed_users = {u.id: u for u in _allowed_l1_users(current_user, db)}
    subordinate = allowed_users.get(subordinate_user_id)
    if not subordinate:
        raise HTTPException(status_code=403, detail="Selected L1 user is outside your reporting hierarchy.")

    outlet = require_outlet_access(
        db, current_user, outlet_id, active_only=True
    )
    allowed_beat_ids = {b.id for p in subordinate.positions if p.is_active for b in p.beats if b.is_active}
    if outlet.beat_id not in allowed_beat_ids:
        raise HTTPException(status_code=403, detail="Outlet is not assigned to the selected L1 user's beats.")

    linked_order = None
    if linked_order_id:
        linked_order = db.query(Order).filter(
            Order.id == linked_order_id,
            Order.user_id == subordinate_user_id,
            Order.outlet_id == outlet_id,
            Order.order_date == ist_today(),
        ).first()
        if not linked_order:
            raise HTTPException(status_code=400, detail="Linked order is not a valid order punched today by the selected L1 user.")
    elif not (no_order_reason or "").strip():
        raise HTTPException(
            status_code=400,
            detail="A no-order reason is required when no order is linked.",
        )

    image_url = None
    if image and image.filename:
        import os
        ext = os.path.splitext(image.filename)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            raise HTTPException(status_code=400, detail="Joint visit evidence must be JPG, PNG, or WEBP.")
        contents = await image.read()
        if len(contents) > 5 * 1024 * 1024:
            raise HTTPException(status_code=400, detail="Joint visit evidence cannot exceed 5MB.")
        from app.utils.s3_service import upload_image_file
        image_url = upload_image_file(
            db,
            contents,
            image.filename,
            folder_prefix="joint_visits",
            content_type=image.content_type or "application/octet-stream",
        )

    visit = VisitRecord(
        user_id=current_user.id,
        outlet_id=outlet_id,
        visit_time=ist_now(),
        notes=notes,
        is_joint_visit=True,
        joint_with_user_id=subordinate.id,
        joint_with_name=subordinate.full_name,
        joint_with_role="L1",
        joint_notes=notes,
        no_order_reason=no_order_reason,
        order_id=linked_order.id if linked_order else None,
        image_url=image_url,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
    )
    db.add(visit)
    db.commit()
    db.refresh(visit)
    return {
        "id": visit.id,
        "outlet_id": visit.outlet_id,
        "subordinate_user_id": subordinate.id,
        "linked_order_id": visit.order_id,
        "image_url": visit.image_url,
        "is_joint_visit": True,
        "message": "Joint visit recorded.",
    }


@router.get("/analytics/eis")
async def get_eis_analytics(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Employee Information System (EIS) analytics for current user."""
    today = ist_today()
    sec_orders = db.query(Order).filter(Order.user_id == current_user.id, Order.order_type == OrderType.secondary).count()
    pri_orders = db.query(Order).filter(Order.user_id == current_user.id, Order.order_type == OrderType.primary).count()
    payments = db.query(Payment).filter(Payment.user_id == current_user.id).count()
    mr_count = db.query(MaterialRequest).filter(MaterialRequest.user_id == current_user.id).count()
    timesheets = db.query(Timesheet).filter(Timesheet.user_id == current_user.id).count()

    return {
        "user_id": current_user.id,
        "full_name": current_user.full_name,
        "role": current_user.role.value,
        "secondary_orders_count": sec_orders,
        "primary_orders_count": pri_orders,
        "payments_count": payments,
        "material_requests_count": mr_count,
        "attendance_days_count": timesheets,
        "working_hours": timesheets * 8,
        "productivity_kpi": "92%",
    }


@router.get("/analytics/mis")
async def get_mis_analytics(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Managerial Information System (MIS) operational outcomes for manager & team."""
    if current_user.role == UserRole.field_rep:
        raise HTTPException(status_code=403, detail="MIS analytics require Managerial role.")

    total_sec_orders = scope_order_query(
        db.query(Order), current_user, db
    ).filter(Order.order_type == OrderType.secondary).count()
    total_pri_orders = scope_order_query(
        db.query(Order), current_user, db
    ).filter(Order.order_type == OrderType.primary).count()
    total_payments = scope_payment_query(db.query(Payment), current_user, db).count()
    total_mrs = scope_material_request_query(
        db.query(MaterialRequest), current_user, db
    ).count()
    total_outlets = scope_outlet_query(db.query(Outlet), current_user, db).count()

    return {
        "manager_id": current_user.id,
        "team_secondary_orders": total_sec_orders,
        "team_primary_orders": total_pri_orders,
        "team_payments_collected": total_payments,
        "team_material_requests": total_mrs,
        "total_outlets_managed": total_outlets,
        "team_productivity_kpi": "88%",
    }
