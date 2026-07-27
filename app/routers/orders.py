import json
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.company import CompanyProfile
from app.models.order import FlowType, Order, OrderItem, OrderStatus, OrderType, SyncStatus, PaymentSettlementStatus
from app.models.outlet import Outlet, OutletStatus
from app.models.payment import Payment, PaymentMethod, PaymentStatus
from app.models.product import Product, ProductCategory
from app.models.timesheet import VisitRecord
from app.models.product_mapping import ProductAliasMap
from app.models.user import User, UserRole
from app.utils.encryption import decrypt
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.utils.ref_generator import order_number

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/operations/orders", tags=["orders"])
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
    products = db.query(Product).filter(Product.is_active == True, Product.category_type == ProductCategory.sales).order_by(Product.name).all()

    return templates.TemplateResponse("orders/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "status": status,
        "pincode": pincode, "partner_id": partner_id, "product_id": product_id,
        "all_time": all_time, "is_filtered_by_days": is_filtered_by_days,
        "partners": partners, "products": products,
        "OrderStatus": OrderStatus, "FlowType": FlowType, "SyncStatus": SyncStatus, "OrderType": OrderType,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def order_new(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    from app.utils.timezone import ist_today

    outlets = db.query(Outlet).filter(Outlet.status == OutletStatus.active).order_by(Outlet.name).all()
    # Confine to Products with Category Scope = Sales
    products = db.query(Product).filter(
        Product.is_active == True,
        Product.category_type == ProductCategory.sales
    ).order_by(Product.name).all()

    from app.models.local_distribution import LocalChannelPartner
    cp_query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)
    if current_user.role == UserRole.territory_manager:
        from app.routers.channel_partners import _get_tm_allowed_geo_ids
        allowed_ids = _get_tm_allowed_geo_ids(db, current_user)
        cp_query = cp_query.filter(LocalChannelPartner.geography_id.in_(allowed_ids))
    channel_partners = cp_query.order_by(LocalChannelPartner.name).all()

    # Active visits today for current user
    active_visits = db.query(VisitRecord).filter(
        VisitRecord.user_id == current_user.id,
        func.date(VisitRecord.visit_time) == ist_today()
    ).order_by(VisitRecord.visit_time.desc()).all()

    return templates.TemplateResponse("orders/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "outlets": outlets, "products": products,
        "channel_partners": channel_partners, "active_visits": active_visits,
        "OrderType": OrderType, "PaymentMethod": PaymentMethod, "error": None,
    })


@router.post("/new")
async def order_create(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    from app.utils.timezone import ist_today, ist_now
    from app.models.local_distribution import LocalChannelPartner
    from app.utils.ref_generator import payment_ref
    from decimal import Decimal

    form = await request.form()
    outlet_id = form.get("outlet_id")
    channel_partner_id = form.get("channel_partner_id")
    order_type_val = form.get("order_type", "Secondary")
    visit_id_val = form.get("visit_id")
    notes = form.get("notes", "")

    amount_collected_val = form.get("amount_collected", "0")
    payment_method_val = form.get("payment_method", "cash")
    transaction_ref_val = form.get("transaction_ref", "")

    product_ids = form.getlist("product_id[]")
    quantities = form.getlist("quantity[]")
    unit_prices = form.getlist("unit_price[]")
    gst_rates = form.getlist("gst_rate[]")
    discount_pcts = form.getlist("discount_pct[]")

    cp_query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)
    if current_user.role == UserRole.territory_manager:
        from app.routers.channel_partners import _get_tm_allowed_geo_ids
        allowed_ids = _get_tm_allowed_geo_ids(db, current_user)
        cp_query = cp_query.filter(LocalChannelPartner.geography_id.in_(allowed_ids))
    channel_partners = cp_query.order_by(LocalChannelPartner.name).all()

    sales_products = db.query(Product).filter(
        Product.is_active == True,
        Product.category_type == ProductCategory.sales
    ).order_by(Product.name).all()
    outlets = db.query(Outlet).filter(Outlet.status == OutletStatus.active).order_by(Outlet.name).all()
    active_visits = db.query(VisitRecord).filter(
        VisitRecord.user_id == current_user.id,
        func.date(VisitRecord.visit_time) == ist_today()
    ).order_by(VisitRecord.visit_time.desc()).all()

    try:
        ot = OrderType(order_type_val)
    except ValueError:
        ot = OrderType.secondary

    # Validate Order Flow Scoping & Targets
    target_outlet_id = None
    target_cp_id = None
    target_visit_id = None
    is_regional = False

    if ot == OrderType.primary:
        # Primary Order: Available ONLY for L2/L3/L4 users (Not L1 field_rep)
        if current_user.role == UserRole.field_rep:
            return templates.TemplateResponse("orders/form.html", {
                "request": request, "current_user": current_user,
                "item": None, "outlets": outlets, "products": sales_products,
                "channel_partners": channel_partners, "active_visits": active_visits,
                "OrderType": OrderType, "PaymentMethod": PaymentMethod,
                "error": "Primary Orders are restricted to Territory Managers and Administrators (L2/L3/L4) only.",
            })

        if not channel_partner_id or channel_partner_id == "regional_company":
            return templates.TemplateResponse("orders/form.html", {
                "request": request, "current_user": current_user,
                "item": None, "outlets": outlets, "products": sales_products,
                "channel_partners": channel_partners, "active_visits": active_visits,
                "OrderType": OrderType, "PaymentMethod": PaymentMethod,
                "error": "Primary Orders must be placed directly against a valid Channel Partner.",
            })
        target_cp_id = int(channel_partner_id) if str(channel_partner_id).isdigit() else None
        target_outlet_id = None
        target_visit_id = None

    else:
        # Secondary Order: Must be associated with an active Visit Record against Outlet
        if not outlet_id or not str(outlet_id).isdigit():
            return templates.TemplateResponse("orders/form.html", {
                "request": request, "current_user": current_user,
                "item": None, "outlets": outlets, "products": sales_products,
                "channel_partners": channel_partners, "active_visits": active_visits,
                "OrderType": OrderType, "PaymentMethod": PaymentMethod,
                "error": "Outlet is required for Secondary Orders.",
            })

        target_outlet_id = int(outlet_id)

        # Retrieve & Verify Mandatory Visit Record
        visit = None
        if visit_id_val and str(visit_id_val).isdigit():
            visit = db.query(VisitRecord).filter(
                VisitRecord.id == int(visit_id_val),
                VisitRecord.user_id == current_user.id
            ).first()
        if not visit:
            visit = db.query(VisitRecord).filter(
                VisitRecord.user_id == current_user.id,
                VisitRecord.outlet_id == target_outlet_id,
                func.date(VisitRecord.visit_time) == ist_today()
            ).order_by(VisitRecord.visit_time.desc()).first()

        if not visit:
            return templates.TemplateResponse("orders/form.html", {
                "request": request, "current_user": current_user,
                "item": None, "outlets": outlets, "products": sales_products,
                "channel_partners": channel_partners, "active_visits": active_visits,
                "OrderType": OrderType, "PaymentMethod": PaymentMethod,
                "error": "A mandatory Visit record against the selected outlet is required for Secondary Orders. Please log an outlet visit first.",
            })

        target_visit_id = visit.id

        if channel_partner_id == "regional_company" or channel_partner_id == "0":
            target_cp_id = None
            is_regional = True
        else:
            target_cp_id = int(channel_partner_id) if channel_partner_id and str(channel_partner_id).isdigit() else None
            is_regional = False

    if not product_ids:
        return templates.TemplateResponse("orders/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "outlets": outlets, "products": sales_products,
            "channel_partners": channel_partners, "active_visits": active_visits,
            "OrderType": OrderType, "PaymentMethod": PaymentMethod,
            "error": "At least one sales product line is required.",
        })

    ord_num = order_number(db, Order)
    o = Order(
        order_number=ord_num,
        outlet_id=target_outlet_id,
        user_id=current_user.id,
        channel_partner_id=target_cp_id,
        is_regional_company=is_regional,
        visit_id=target_visit_id,
        company_profile_id=current_user.company_profile_id,
        order_type=ot,
        flow_type=FlowType.zap_invoice,
        sync_status=SyncStatus.not_applicable,
        status=OrderStatus.submitted,
        notes=notes or None,
    )
    db.add(o)
    db.flush()

    for i, pid in enumerate(product_ids):
        if not pid or not str(pid).isdigit():
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

    db.flush()
    db.refresh(o)

    # Process Payments Flow for Secondary Orders fulfilled by Regional Company
    if ot == OrderType.secondary and is_regional:
        amt_col = float(amount_collected_val) if amount_collected_val else 0.0
        if amt_col > 0:
            pay_ref_str = payment_ref(db, Payment)
            pm = PaymentMethod(payment_method_val) if payment_method_val in [m.value for m in PaymentMethod] else PaymentMethod.cash
            pay = Payment(
                payment_ref=pay_ref_str,
                order_id=o.id,
                outlet_id=o.outlet_id,
                user_id=current_user.id,
                amount=Decimal(str(amt_col)),
                method=pm,
                transaction_ref=transaction_ref_val or None,
                status=PaymentStatus.collected,
                collected_at=ist_now(),
            )
            db.add(pay)
            db.flush()

        # Update Payment Settlement Status
        order_total_val = float(o.total_amount)
        if amt_col >= order_total_val and order_total_val > 0:
            o.payment_settlement = PaymentSettlementStatus.paid
        elif amt_col > 0:
            o.payment_settlement = PaymentSettlementStatus.partial
        else:
            o.payment_settlement = PaymentSettlementStatus.unpaid

    db.commit()
    db.refresh(o)

    # Auto-allocate channel partner & record creation history log
    from app.services.channel_partner_notification import auto_allocate_channel_partner_for_order, record_order_history_log
    if not is_regional and o.channel_partner_id:
        auto_allocate_channel_partner_for_order(db, o)

    record_order_history_log(
        db=db,
        order_id=o.id,
        action="created",
        performed_by_id=current_user.id,
        new_status=o.status.value,
        channel_partner_id=o.channel_partner_id,
        notes=f"{o.order_type.value} Order {o.order_number} created" + (f" for outlet {o.outlet.name}" if o.outlet else f" for partner {o.channel_partner.name if o.channel_partner else 'N/A'}")
    )

    set_flash_success(request, f"{o.order_type.value} Order {ord_num} created successfully.")
    return RedirectResponse(f"/operations/orders/{o.id}", status_code=302)


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
        return RedirectResponse("/operations/orders", status_code=302)

    # Ensure channel partner is auto-allocated if missing
    if not item.channel_partner_id:
        from app.services.channel_partner_notification import auto_allocate_channel_partner_for_order
        auto_allocate_channel_partner_for_order(db, item)

    from app.models.local_distribution import LocalChannelPartner
    cp_query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)
    if current_user.role == UserRole.territory_manager:
        from app.routers.channel_partners import _get_tm_allowed_geo_ids
        allowed_ids = _get_tm_allowed_geo_ids(db, current_user)
        cp_query = cp_query.filter(LocalChannelPartner.geography_id.in_(allowed_ids))
    available_channel_partners = cp_query.order_by(LocalChannelPartner.name).all()

    from app.models.payment import Payment
    payments = db.query(Payment).filter(Payment.order_id == order_id).order_by(Payment.created_at.desc()).all()
    total_paid = sum(p.amount for p in payments) if payments else Decimal("0")

    return templates.TemplateResponse("orders/detail.html", {
        "request": request, "current_user": current_user,
        "item": item, "payments": payments, "total_paid": total_paid,
        "available_channel_partners": available_channel_partners,
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
        return RedirectResponse("/operations/orders", status_code=302)

    try:
        amt_val = Decimal(amount)
    except Exception:
        set_flash_error(request, "Invalid payment amount.")
        return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)

    # Denomination validation for cash
    denom_json = None
    if payment_mode == "cash":
        calculated_total = (count_500 * 500) + (count_200 * 200) + (count_100 * 100) + (count_50 * 50) + (count_20 * 20) + (count_10 * 10)
        if Decimal(calculated_total) != amt_val:
            set_flash_error(request, f"Cash denomination total (₹{calculated_total}) does not match payment amount (₹{amt_val}).")
            return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)
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
    return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)


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
        return RedirectResponse("/operations/orders", status_code=302)
    try:
        old_status_val = item.status.value if item.status else None
        item.status = OrderStatus(new_status)

        # Trigger instant notification to channel partners upon approval ('confirmed')
        if new_status == "confirmed":
            from app.services.channel_partner_notification import trigger_instant_order_notification
            trigger_instant_order_notification(db, item)

        # Record History Log
        from app.services.channel_partner_notification import record_order_history_log
        record_order_history_log(
            db=db,
            order_id=item.id,
            action="status_changed",
            performed_by_id=current_user.id,
            old_status=old_status_val,
            new_status=new_status,
            channel_partner_id=item.channel_partner_id,
            notes=f"Order status updated from '{old_status_val}' to '{new_status}' by {current_user.full_name}"
        )

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
    return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)


@router.post("/{order_id}/allocate-channel-partner")
async def order_allocate_channel_partner(
    order_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    channel_partner_id: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
):
    item = db.query(Order).filter(Order.id == order_id).first()
    if not item:
        set_flash_error(request, "Order not found.")
        return RedirectResponse("/operations/orders", status_code=302)

    cp_id_int = int(channel_partner_id) if channel_partner_id and str(channel_partner_id).isdigit() else None
    from app.models.local_distribution import LocalChannelPartner
    cp = db.query(LocalChannelPartner).filter(LocalChannelPartner.id == cp_id_int).first() if cp_id_int else None

    old_cp_id = item.channel_partner_id
    item.channel_partner_id = cp.id if cp else None
    db.commit()

    from app.services.channel_partner_notification import record_order_history_log, trigger_instant_order_notification
    cp_name = cp.name if cp else "Unassigned"
    action_type = "channel_partner_reassigned_post_approval" if item.status == OrderStatus.confirmed else "channel_partner_allocated"
    record_order_history_log(
        db=db,
        order_id=item.id,
        action=action_type,
        performed_by_id=current_user.id,
        old_status=item.status.value,
        new_status=item.status.value,
        channel_partner_id=item.channel_partner_id,
        notes=notes or f"Fulfillment allocated/reassigned to Channel Partner: '{cp_name}' by {current_user.full_name}"
    )

    # If order is already approved ('confirmed'), trigger notification to the newly assigned channel partner
    if item.status == OrderStatus.confirmed:
        trigger_instant_order_notification(db, item)

    set_flash_success(request, f"Fulfillment allocated to Channel Partner '{cp_name}'.")
    return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)


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
        return RedirectResponse("/operations/orders", status_code=302)

    if item.flow_type != FlowType.connect:
        set_flash_error(request, "This order does not use the CONNECT flow.")
        return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)

    if item.status not in (OrderStatus.submitted, OrderStatus.confirmed):
        set_flash_error(request, "Order must be submitted or confirmed to sync to CONNECT.")
        return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)

    item.sync_status = SyncStatus.pending
    item.sync_error = None
    db.commit()

    await _sync_order_to_connect(item, db)
    return RedirectResponse(f"/operations/orders/{order_id}", status_code=302)


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
