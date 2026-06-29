from datetime import date, timedelta

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.expense import Expense, ExpenseStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.timesheet import Timesheet, VisitRecord
from app.models.user import User, UserRole
from app.models.outlet import Outlet
from app.models.product import Product
from app.utils.flash import get_flash, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/analytics", tags=["analytics"])
templates = Jinja2Templates(directory="app/templates")

_ADMIN_MANAGER = require_web_roles(UserRole.admin, UserRole.territory_manager)


@router.get("", response_class=RedirectResponse)
async def analytics_root():
    return RedirectResponse("/analytics/sales", status_code=302)


# ── Sales Analytics ────────────────────────────────────────────────────────────

@router.get("/sales", response_class=HTMLResponse)
async def sales_page(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=365),
):
    # Summary KPIs
    since = date.today() - timedelta(days=days)
    active_statuses = [OrderStatus.confirmed, OrderStatus.dispatched, OrderStatus.delivered]

    total_revenue = db.query(
        func.sum(OrderItem.unit_price * OrderItem.quantity * (1 - OrderItem.discount_pct / 100))
    ).join(Order).filter(
        Order.status.in_(active_statuses),
        Order.order_date >= since,
    ).scalar() or 0

    total_orders = db.query(func.count(Order.id)).filter(
        Order.order_date >= since,
        Order.status != OrderStatus.cancelled,
    ).scalar() or 0

    total_payments = db.query(func.sum(Payment.amount)).filter(
        Payment.status == PaymentStatus.verified,
        Payment.collected_at >= str(since),
    ).scalar() or 0

    pending_orders = db.query(func.count(Order.id)).filter(
        Order.status == OrderStatus.submitted,
    ).scalar() or 0

    return templates.TemplateResponse("analytics/sales.html", {
        "request": request, "current_user": current_user,
        "days": days,
        "total_revenue": round(float(total_revenue), 2),
        "total_orders": total_orders,
        "total_payments": round(float(total_payments), 2),
        "pending_orders": pending_orders,
        **get_flash(request),
    })


@router.get("/sales/data")
async def sales_data(
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=365),
):
    since = date.today() - timedelta(days=days)
    active_statuses = [OrderStatus.confirmed, OrderStatus.dispatched, OrderStatus.delivered]

    # Revenue & order count by day
    daily_rows = db.query(
        Order.order_date.label("day"),
        func.sum(
            OrderItem.unit_price * OrderItem.quantity * (1 - OrderItem.discount_pct / 100)
        ).label("revenue"),
        func.count(Order.id.distinct()).label("orders"),
    ).join(OrderItem, OrderItem.order_id == Order.id).filter(
        Order.status.in_(active_statuses),
        Order.order_date >= since,
    ).group_by(Order.order_date).order_by(Order.order_date).all()

    daily = {
        "labels": [str(r.day) for r in daily_rows],
        "revenue": [round(float(r.revenue), 2) for r in daily_rows],
        "orders": [r.orders for r in daily_rows],
    }

    # Orders by status
    status_rows = db.query(
        Order.status, func.count(Order.id)
    ).group_by(Order.status).all()
    orders_by_status = {r[0].value: r[1] for r in status_rows}

    # Top 10 outlets by revenue
    outlet_rows = db.query(
        Outlet.name,
        func.sum(
            OrderItem.unit_price * OrderItem.quantity * (1 - OrderItem.discount_pct / 100)
        ).label("rev"),
    ).join(Order, Order.outlet_id == Outlet.id).join(
        OrderItem, OrderItem.order_id == Order.id
    ).filter(
        Order.status.in_(active_statuses),
        Order.order_date >= since,
    ).group_by(Outlet.id, Outlet.name).order_by(func.sum(
        OrderItem.unit_price * OrderItem.quantity * (1 - OrderItem.discount_pct / 100)
    ).desc()).limit(10).all()

    top_outlets = {
        "labels": [r.name for r in outlet_rows],
        "revenue": [round(float(r.rev), 2) for r in outlet_rows],
    }

    # Top 10 products by quantity sold
    product_rows = db.query(
        Product.name,
        func.sum(OrderItem.quantity).label("qty"),
    ).join(OrderItem, OrderItem.product_id == Product.id).join(
        Order, Order.id == OrderItem.order_id
    ).filter(
        Order.status.in_(active_statuses),
        Order.order_date >= since,
    ).group_by(Product.id, Product.name).order_by(
        func.sum(OrderItem.quantity).desc()
    ).limit(10).all()

    top_products = {
        "labels": [r.name for r in product_rows],
        "qty": [int(r.qty) for r in product_rows],
    }

    return JSONResponse({
        "daily": daily,
        "orders_by_status": orders_by_status,
        "top_outlets": top_outlets,
        "top_products": top_products,
    })


# ── Rep Performance ─────────────────────────────────────────────────────────────

@router.get("/reps", response_class=HTMLResponse)
async def reps_page(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=365),
):
    return templates.TemplateResponse("analytics/reps.html", {
        "request": request, "current_user": current_user,
        "days": days, **get_flash(request),
    })


@router.get("/reps/data")
async def reps_data(
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=365),
):
    since = date.today() - timedelta(days=days)
    active_statuses = [OrderStatus.confirmed, OrderStatus.dispatched, OrderStatus.delivered]

    reps = db.query(User).filter(
        User.role == UserRole.field_rep, User.is_active == True
    ).order_by(User.full_name).all()

    results = []
    for rep in reps:
        # Orders & revenue
        order_rows = db.query(
            func.count(Order.id.distinct()).label("cnt"),
            func.coalesce(func.sum(
                OrderItem.unit_price * OrderItem.quantity * (1 - OrderItem.discount_pct / 100)
            ), 0).label("rev"),
        ).outerjoin(OrderItem, OrderItem.order_id == Order.id).filter(
            Order.user_id == rep.id,
            Order.status.in_(active_statuses),
            Order.order_date >= since,
        ).first()

        order_count = order_rows.cnt if order_rows else 0
        revenue = round(float(order_rows.rev), 2) if order_rows else 0.0

        # Visits
        visit_count = db.query(func.count(VisitRecord.id)).filter(
            VisitRecord.user_id == rep.id,
            VisitRecord.visit_time >= str(since),
        ).scalar() or 0

        out_of_range = db.query(func.count(VisitRecord.id)).filter(
            VisitRecord.user_id == rep.id,
            VisitRecord.visit_time >= str(since),
            VisitRecord.distance_from_outlet > 200,
        ).scalar() or 0

        # Attendance days
        attendance_days = db.query(func.count(Timesheet.id)).filter(
            Timesheet.user_id == rep.id,
            Timesheet.work_date >= since,
        ).scalar() or 0

        # Expenses
        expense_total = db.query(func.coalesce(func.sum(Expense.amount), 0)).filter(
            Expense.user_id == rep.id,
            Expense.status == ExpenseStatus.approved,
            Expense.expense_date >= since,
        ).scalar() or 0

        results.append({
            "name": rep.full_name,
            "orders": order_count,
            "revenue": revenue,
            "visits": visit_count,
            "out_of_range": out_of_range,
            "attendance_days": attendance_days,
            "expenses": round(float(expense_total), 2),
        })

    # Sort by revenue desc
    results.sort(key=lambda r: r["revenue"], reverse=True)
    return JSONResponse({"reps": results, "days": days})


# ── Marketing Performance ───────────────────────────────────────────────────────

@router.get("/marketing", response_class=HTMLResponse)
async def marketing_page(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=365),
):
    from app.models.asset_capitalization import AssetCapitalization, ACStatus
    from app.models.material_request import MaterialRequest, MRStatus

    since = date.today() - timedelta(days=days)

    # Marketing KPI Summary
    total_assets = db.query(func.sum(AssetCapitalization.quantity)).filter(
        AssetCapitalization.status == ACStatus.deployed,
        AssetCapitalization.created_at >= since
    ).scalar() or 0

    pending_mrs = db.query(func.count(MaterialRequest.id)).filter(
        MaterialRequest.status.in_([MRStatus.submitted, MRStatus.acknowledged]),
        MaterialRequest.created_at >= since
    ).scalar() or 0

    total_mrs = db.query(func.count(MaterialRequest.id)).filter(
        MaterialRequest.created_at >= since
    ).scalar() or 0

    return templates.TemplateResponse("analytics/marketing.html", {
        "request": request, "current_user": current_user,
        "days": days,
        "total_assets": int(total_assets),
        "pending_mrs": pending_mrs,
        "total_mrs": total_mrs,
        **get_flash(request),
    })


@router.get("/marketing/data")
async def marketing_data(
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    days: int = Query(default=30, ge=7, le=365),
):
    from app.models.asset_capitalization import AssetCapitalization, ACStatus
    from app.models.material_request import MaterialRequest

    since = date.today() - timedelta(days=days)

    # Assets Deployed by Name
    asset_rows = db.query(
        AssetCapitalization.item_name,
        func.sum(AssetCapitalization.quantity)
    ).filter(
        AssetCapitalization.status == ACStatus.deployed,
        AssetCapitalization.created_at >= since
    ).group_by(AssetCapitalization.item_name).order_by(func.sum(AssetCapitalization.quantity).desc()).limit(10).all()

    top_assets = {
        "labels": [r[0] for r in asset_rows],
        "quantity": [int(r[1]) for r in asset_rows],
    }

    # MRs by Status
    mr_rows = db.query(
        MaterialRequest.status,
        func.count(MaterialRequest.id)
    ).filter(
        MaterialRequest.created_at >= since
    ).group_by(MaterialRequest.status).all()

    mrs_by_status = {r[0].value: r[1] for r in mr_rows}

    return JSONResponse({
        "top_assets": top_assets,
        "mrs_by_status": mrs_by_status,
        "days": days
    })


# ── Alerts ─────────────────────────────────────────────────────────────────────

@router.get("/alerts/unread-count")
async def alerts_unread_count(
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
):
    count = db.query(func.count(Alert.id)).filter(Alert.is_read == False).scalar() or 0
    return JSONResponse({"count": count})


@router.get("/alerts", response_class=HTMLResponse)
async def alerts_page(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
    severity: str = Query(default=""),
    show_read: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Alert)
    if not show_read:
        query = query.filter(Alert.is_read == False)
    if severity:
        query = query.filter(Alert.severity == severity)
    query = query.order_by(Alert.created_at.desc())
    pagination = paginate(query, page)

    unread_count = db.query(func.count(Alert.id)).filter(Alert.is_read == False).scalar() or 0

    return templates.TemplateResponse("analytics/alerts.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "severity": severity,
        "show_read": show_read, "unread_count": unread_count,
        "AlertSeverity": AlertSeverity,
        **get_flash(request),
    })


@router.post("/alerts/{alert_id}/dismiss", response_class=RedirectResponse)
async def dismiss_alert(
    alert_id: int, request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert:
        alert.is_read = True
        db.commit()
    return RedirectResponse("/analytics/alerts", status_code=302)


@router.post("/alerts/dismiss-all", response_class=RedirectResponse)
async def dismiss_all_alerts(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
):
    db.query(Alert).filter(Alert.is_read == False).update({"is_read": True})
    db.commit()
    set_flash_success(request, "All alerts dismissed.")
    return RedirectResponse("/analytics/alerts", status_code=302)
