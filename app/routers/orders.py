import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.company import CompanyProfile
from app.models.order import FlowType, Order, OrderItem, OrderStatus, SyncStatus
from app.models.outlet import Outlet, OutletStatus
from app.models.product import Product
from app.models.product_mapping import ProductAliasMap
from app.models.user import User, UserRole
from app.utils.encryption import decrypt
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.utils.ref_generator import order_number

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/orders", tags=["orders"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def order_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    status: str = Query(default=""),
    pincode: str = Query(default=""),
    partner_id: str = Query(default=""),
    product_id: str = Query(default=""),
    all_time: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    from datetime import timedelta
    from app.models.local_distribution import LocalChannelPartner

    query = db.query(Order)
    if current_user.role == UserRole.field_rep:
        query = query.filter(Order.user_id == current_user.id)
    if q:
        query = query.filter(Order.order_number.ilike(f"%{q}%"))
    if status and status in [s.value for s in OrderStatus]:
        query = query.filter(Order.status == status)

    # 7-day default cap
    is_filtered_by_days = False
    if not all_time and not q:
        seven_days_ago = datetime.utcnow() - timedelta(days=7)
        query = query.filter(Order.created_at >= seven_days_ago)
        is_filtered_by_days = True

    if pincode:
        query = query.join(Outlet, Order.outlet_id == Outlet.id).filter(Outlet.pincode.ilike(f"%{pincode}%"))

    if partner_id:
        # Filter orders associated with channel partner outlets
        query = query.join(Outlet, Order.outlet_id == Outlet.id).filter(Outlet.channel_partner_id == int(partner_id))

    if product_id:
        query = query.join(OrderItem, Order.id == OrderItem.order_id).filter(OrderItem.product_id == int(product_id))

    query = query.order_by(Order.created_at.desc())
    pagination = paginate(query, page)

    partners = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True).order_by(LocalChannelPartner.name).all()
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.name).all()

    return templates.TemplateResponse("orders/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "status": status,
        "pincode": pincode, "partner_id": partner_id, "product_id": product_id,
        "all_time": all_time, "is_filtered_by_days": is_filtered_by_days,
        "partners": partners, "products": products,
        "OrderStatus": OrderStatus, "FlowType": FlowType, "SyncStatus": SyncStatus,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def order_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    outlets = db.query(Outlet).filter(Outlet.status == OutletStatus.active).order_by(Outlet.name).all()
    products = db.query(Product).filter(Product.is_active == True).order_by(Product.name).all()
    return templates.TemplateResponse("orders/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "outlets": outlets, "products": products,
        "FlowType": FlowType, "error": None,
    })


@router.post("/new")
async def order_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    form = await request.form()
    outlet_id = form.get("outlet_id")
    notes = form.get("notes", "")
    flow_type_val = form.get("flow_type", "zap_invoice")
    product_ids = form.getlist("product_id[]")
    quantities = form.getlist("quantity[]")
    unit_prices = form.getlist("unit_price[]")
    gst_rates = form.getlist("gst_rate[]")
    discount_pcts = form.getlist("discount_pct[]")

    if not outlet_id or not product_ids:
        outlets = db.query(Outlet).filter(Outlet.status == OutletStatus.active).order_by(Outlet.name).all()
        products = db.query(Product).filter(Product.is_active == True).order_by(Product.name).all()
        return templates.TemplateResponse("orders/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "outlets": outlets, "products": products,
            "FlowType": FlowType,
            "error": "Outlet and at least one product are required.",
        })

    try:
        ft = FlowType(flow_type_val)
    except ValueError:
        ft = FlowType.zap_invoice

    ord_num = order_number(db, Order)
    o = Order(
        order_number=ord_num,
        outlet_id=int(outlet_id),
        user_id=current_user.id,
        company_profile_id=current_user.company_profile_id,
        flow_type=ft,
        sync_status=SyncStatus.not_applicable,
        status=OrderStatus.draft,
        notes=notes or None,
    )
    db.add(o)
    db.flush()

    for i, pid in enumerate(product_ids):
        if not pid:
            continue
        try:
            db.add(OrderItem(
                order_id=o.id,
                product_id=int(pid),
                quantity=int(quantities[i]) if i < len(quantities) else 1,
                unit_price=float(unit_prices[i]) if i < len(unit_prices) else 0,
                gst_rate=float(gst_rates[i]) if i < len(gst_rates) else 0,
                discount_pct=float(discount_pcts[i]) if i < len(discount_pcts) else 0,
            ))
        except (ValueError, IndexError):
            continue

    db.commit()
    set_flash_success(request, f"Order {ord_num} created.")
    return RedirectResponse("/orders", status_code=302)


@router.get("/{order_id}", response_class=HTMLResponse)
async def order_detail(
    order_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    q = db.query(Order).filter(Order.id == order_id)
    if current_user.role == UserRole.field_rep:
        q = q.filter(Order.user_id == current_user.id)
    item = q.first()
    if not item:
        set_flash_error(request, "Order not found.")
        return RedirectResponse("/orders", status_code=302)
    from app.models.payment import Payment
    payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.created_at.desc()).all()
    total_paid = sum(p.amount for p in payments) if payments else Decimal("0")

    return templates.TemplateResponse("orders/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "payments": payments, "total_paid": total_paid,
        "OrderStatus": OrderStatus, "FlowType": FlowType, "SyncStatus": SyncStatus,
        **get_flash(request),
    })


@router.post("/{order_id}/record-payment")
async def order_record_payment(
    order_id: int, request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    payment_mode: str = Form("cash"),
    amount: str = Form("0"),
    reference_no: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
    count_500: int = Form(default=0),
    count_200: int = Form(default=0),
    count_100: int = Form(default=0),
    count_50: int = Form(default=0),
    count_20: int = Form(default=0),
    count_10: int = Form(default=0),
):
    item = db.query(Order).filter(Order.id == order_id).first()
    if not item:
        set_flash_error(request, "Order not found.")
        return RedirectResponse("/orders", status_code=302)

    try:
        amt_val = Decimal(amount)
    except Exception:
        set_flash_error(request, "Invalid payment amount.")
        return RedirectResponse(f"/orders/{order_id}", status_code=302)

    # Denomination validation for cash
    denom_json = None
    if payment_mode == "cash":
        calculated_total = (count_500 * 500) + (count_200 * 200) + (count_100 * 100) + (count_50 * 50) + (count_20 * 20) + (count_10 * 10)
        if Decimal(calculated_total) != amt_val:
            set_flash_error(request, f"Cash denomination total (₹{calculated_total}) does not match payment amount (₹{amt_val}).")
            return RedirectResponse(f"/orders/{order_id}", status_code=302)
        denom_json = json.dumps({
            "500": count_500, "200": count_200, "100": count_100,
            "50": count_50, "20": count_20, "10": count_10
        })

    from app.models.payment import Payment, PaymentMode
    pm_enum = PaymentMode(payment_mode) if payment_mode in [m.value for m in PaymentMode] else PaymentMode.cash

    payment = Payment(
        order_id=item.id,
        outlet_id=item.outlet_id,
        user_id=current_user.id,
        company_profile_id=item.company_profile_id,
        amount=amt_val,
        payment_mode=pm_enum,
        reference_no=reference_no or None,
        denomination_breakdown=denom_json,
        notes=notes or None,
    )
    db.add(payment)
    db.commit()

    set_flash_success(request, f"Payment of ₹{amt_val} recorded for order {item.order_number}.")
    return RedirectResponse(f"/orders/{order_id}", status_code=302)


@router.post("/{order_id}/status")
async def order_update_status(
    order_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    new_status: str = Form(...),
):
    item = db.query(Order).filter(Order.id == order_id).first()
    if not item:
        set_flash_error(request, "Order not found.")
        return RedirectResponse("/orders", status_code=302)
    try:
        item.status = OrderStatus(new_status)

        # Auto-trigger CONNECT sync when confirming a CONNECT order
        if new_status == "confirmed" and item.flow_type == FlowType.connect:
            item.sync_status = SyncStatus.pending
            db.commit()
            await _sync_order_to_connect(item, db)
        else:
            db.commit()

        set_flash_success(request, f"Order {item.order_number} status → {new_status}.")
    except ValueError:
        set_flash_error(request, f"Invalid status '{new_status}'.")
    return RedirectResponse(f"/orders/{order_id}", status_code=302)


@router.post("/{order_id}/sync-connect")
async def order_sync_connect(
    order_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    """Manually (re-)submit an order to CONNECT."""
    item = db.query(Order).filter(Order.id == order_id).first()
    if not item:
        set_flash_error(request, "Order not found.")
        return RedirectResponse("/orders", status_code=302)

    if item.flow_type != FlowType.connect:
        set_flash_error(request, "This order does not use the CONNECT flow.")
        return RedirectResponse(f"/orders/{order_id}", status_code=302)

    if item.status not in (OrderStatus.submitted, OrderStatus.confirmed):
        set_flash_error(request, "Order must be submitted or confirmed to sync to CONNECT.")
        return RedirectResponse(f"/orders/{order_id}", status_code=302)

    item.sync_status = SyncStatus.pending
    item.sync_error = None
    db.commit()

    await _sync_order_to_connect(item, db)
    return RedirectResponse(f"/orders/{order_id}", status_code=302)


async def _sync_order_to_connect(order: Order, db: Session) -> None:
    """Internal helper: push an order to CONNECT and update status dynamically."""
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == order.company_profile_id).first()
    if not profile or not profile.connect_base_url:
        raise ValueError("CONNECT configuration missing for this company profile.")

    api_key_secret = decrypt(profile.connect_api_key_encrypted)

    items_payload = []
    for it in order.items:
        alias = db.query(ProductAliasMap).filter(
            ProductAliasMap.company_profile_id == order.company_profile_id,
            ProductAliasMap.product_id == it.product_id
        ).first()

        connect_code = alias.connect_item_code if alias else (it.product.sku or it.product.erp_id)
        items_payload.append({
            "item": connect_code,
            "quantity": it.quantity,
            "item_rate": float(it.unit_price),
            "line_item_amount": float(it.line_total)
        })

    payload = {
        "order_date": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ordered_by": order.user.email,
        "agent_code": order.user.employee_id or order.user.username,
        "delivery_address": order.outlet.name,
        "contact": order.outlet.owner_name or "N/A",
        "service_category": order.outlet.channel.value if (order.outlet and order.outlet.channel) else "General",
        "channel_partner": "",
        "order_notes": order.notes or "",
        "items": items_payload,
        "timeline": [
            {
                "event_type": "Status Update",
                "recorded_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "fieldname": "order_status",
                "from_value": "Submitted",
                "to_value": "Assigned",
                "created_by": order.user.email
            }
        ]
    }

    dynamic_adapter = ConnectAdapter(
        base_url=profile.connect_base_url,
        api_key=api_key_secret
    )

    try:
        result = await dynamic_adapter.submit_order(payload)
        order.sync_status = SyncStatus.synced
        order.connect_ref = result.get("data", {}).get("name") or result.get("name") or str(result)
        order.sync_error = None
        order.sync_retries = 0
        db.commit()
        logger.info("CONNECT sync success — order %s → ref %s", order.order_number, order.connect_ref)
    except Exception as exc:
        order.sync_status = SyncStatus.failed
        order.sync_error = str(exc)[:1000]
        order.sync_retries += 1
        db.add(Alert(
            severity=AlertSeverity.critical,
            alert_type=AlertType.sync_failure,
            title=f"CONNECT sync failed: {order.order_number}",
            message=f"Order {order.order_number} failed to sync to CONNECT: {str(exc)[:500]}",
        ))
        db.commit()
        logger.error("CONNECT sync failed — order %s: %s", order.order_number, exc)
