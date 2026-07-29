from typing import Optional

from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.order import Order, OrderStatus, PaymentSettlementStatus
from app.models.outlet import Outlet, OutletStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.utils.ref_generator import payment_ref
from app.services.access_control import (
    require_order_access,
    require_outlet_access,
    require_payment_access,
    scope_order_query,
    scope_outlet_query,
    scope_payment_query,
)

router = APIRouter(prefix="/payments", tags=["payments"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def payment_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    status: str = Query(default=""),
    method: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = scope_payment_query(db.query(Payment), current_user, db)
    if q:
        query = query.filter(Payment.payment_ref.ilike(f"%{q}%"))
    if status and status in [s.value for s in PaymentStatus]:
        query = query.filter(Payment.status == status)
    if method and method in [m.value for m in PaymentMethod]:
        query = query.filter(Payment.method == method)
    query = query.order_by(Payment.created_at.desc())
    pagination = paginate(query, page)
    return templates.TemplateResponse("payments/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "status": status, "method": method,
        "PaymentStatus": PaymentStatus, "PaymentMethod": PaymentMethod,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def payment_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    order_id: Optional[str] = Query(default=None),
):
    outlets = scope_outlet_query(
        db.query(Outlet).filter(Outlet.status == OutletStatus.active), current_user, db
    ).order_by(Outlet.name).all()
    selected_order = require_order_access(db, current_user, int(order_id)) if order_id else None
    
    # Fetch unpaid/partially-paid native orders.
    unpaid_orders = (
        scope_order_query(db.query(Order), current_user, db)
        .filter(
            Order.status != OrderStatus.cancelled,
            Order.payment_settlement.in_([PaymentSettlementStatus.unpaid, PaymentSettlementStatus.partial])
        )
        .order_by(Order.order_date.asc())
        .all()
    )
    
    return templates.TemplateResponse("payments/form.html", {
        "request": request, "current_user": current_user,
        "outlets": outlets, "selected_order": selected_order,
        "unpaid_orders": unpaid_orders,
        "PaymentMethod": PaymentMethod, "error": None,
    })


@router.post("/new")
async def payment_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    outlet_id: str = Form(...),
    amount: str = Form(...),
    method: str = Form(...),
    order_id: Optional[str] = Form(default=None),
    transaction_ref: Optional[str] = Form(default=None),
    denom_500: int = Form(default=0),
    denom_200: int = Form(default=0),
    denom_100: int = Form(default=0),
    denom_50: int = Form(default=0),
    denom_20: int = Form(default=0),
    denom_10: int = Form(default=0),
):
    try:
        require_outlet_access(db, current_user, int(outlet_id), active_only=True)
    except (HTTPException, ValueError):
        set_flash_error(request, "Outlet not found.")
        return RedirectResponse("/payments/new", status_code=302)
    try:
        amt = float(amount)
        pay_method = PaymentMethod(method)
    except ValueError:
        outlets = scope_outlet_query(
            db.query(Outlet).filter(Outlet.status == OutletStatus.active),
            current_user,
            db,
        ).order_by(Outlet.name).all()
        unpaid_orders = (
            scope_order_query(db.query(Order), current_user, db)
            .filter(
                Order.status != OrderStatus.cancelled,
                Order.payment_settlement.in_([PaymentSettlementStatus.unpaid, PaymentSettlementStatus.partial])
            )
            .order_by(Order.order_date.asc())
            .all()
        )
        return templates.TemplateResponse("payments/form.html", {
            "request": request, "current_user": current_user,
            "outlets": outlets, "selected_order": None,
            "unpaid_orders": unpaid_orders,
            "PaymentMethod": PaymentMethod, "error": "Invalid amount or payment method.",
        })

    target_order_id = int(order_id) if (order_id and order_id.strip() != "") else None
    if target_order_id:
        try:
            require_order_access(db, current_user, target_order_id)
        except HTTPException:
            set_flash_error(request, "Order not found.")
            return RedirectResponse("/payments/new", status_code=302)
    if not target_order_id:
        # Find the oldest unpaid or partial order for this outlet to auto-link.
        oldest_unpaid = (
            db.query(Order)
            .filter(
                Order.outlet_id == int(outlet_id),
                Order.status != OrderStatus.cancelled,
                Order.payment_settlement.in_([PaymentSettlementStatus.unpaid, PaymentSettlementStatus.partial])
            )
            .order_by(Order.order_date.asc(), Order.created_at.asc())
            .first()
        )
        if oldest_unpaid:
            target_order_id = oldest_unpaid.id

    ref = payment_ref(db, Payment)
    p = Payment(
        payment_ref=ref,
        outlet_id=int(outlet_id),
        user_id=current_user.id,
        order_id=target_order_id,
        amount=amt,
        method=pay_method,
        transaction_ref=transaction_ref or None,
        status=PaymentStatus.collected,
        denom_500=denom_500, denom_200=denom_200, denom_100=denom_100,
        denom_50=denom_50, denom_20=denom_20, denom_10=denom_10,
    )
    db.add(p)
    db.commit()

    # Recalculate settlement on linked order
    if p.order_id:
        order = p.order
        total_paid = sum(
            float(pay.amount)
            for pay in order.payments
            if pay.status in (PaymentStatus.collected, PaymentStatus.verified)
        )
        if total_paid <= 0:
            order.payment_settlement = PaymentSettlementStatus.unpaid
        elif total_paid >= float(order.total_amount):
            order.payment_settlement = PaymentSettlementStatus.paid
        else:
            order.payment_settlement = PaymentSettlementStatus.partial
        db.commit()

    set_flash_success(request, f"Payment {ref} recorded.")
    return RedirectResponse("/payments", status_code=302)


@router.post("/{payment_id}/verify")
async def payment_verify(
    payment_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = require_payment_access(db, current_user, payment_id)
    if item.status != PaymentStatus.collected:
        raise HTTPException(status_code=409, detail="Payment is not awaiting verification.")
    item.status = PaymentStatus.verified
    db.commit()
        
    # Recalculate linked order
    if item.order_id:
        order = item.order
        total_paid = sum(
            float(pay.amount)
            for pay in order.payments
            if pay.status in (PaymentStatus.collected, PaymentStatus.verified)
        )
        if total_paid <= 0:
            order.payment_settlement = PaymentSettlementStatus.unpaid
        elif total_paid >= float(order.total_amount):
            order.payment_settlement = PaymentSettlementStatus.paid
        else:
            order.payment_settlement = PaymentSettlementStatus.partial
        db.commit()

    set_flash_success(request, f"Payment {item.payment_ref} verified.")
    return RedirectResponse("/payments", status_code=302)


@router.post("/{payment_id}/reject")
async def payment_reject(
    payment_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = require_payment_access(db, current_user, payment_id)
    if item.status not in (PaymentStatus.collected, PaymentStatus.pending):
        raise HTTPException(status_code=409, detail="Payment is not awaiting review.")
    item.status = PaymentStatus.rejected
    db.commit()
        
    # Recalculate linked order
    if item.order_id:
        order = item.order
        total_paid = sum(
            float(pay.amount)
            for pay in order.payments
            if pay.status in (PaymentStatus.collected, PaymentStatus.verified)
        )
        if total_paid <= 0:
            order.payment_settlement = PaymentSettlementStatus.unpaid
        elif total_paid >= float(order.total_amount):
            order.payment_settlement = PaymentSettlementStatus.paid
        else:
            order.payment_settlement = PaymentSettlementStatus.partial
        db.commit()

    set_flash_error(request, f"Payment {item.payment_ref} rejected.")
    return RedirectResponse("/payments", status_code=302)
