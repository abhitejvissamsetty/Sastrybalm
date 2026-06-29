from datetime import date

from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth
from app.models.alert import Alert
from app.models.expense import Expense, ExpenseStatus
from app.models.material_request import MaterialRequest, MRStatus
from app.models.order import Order, OrderItem, OrderStatus
from app.models.outlet import Outlet, OutletStatus
from app.models.payment import Payment, PaymentStatus
from app.models.product import Product
from app.models.company import CompanyProfile
from app.models.timesheet import Timesheet, VisitRecord
from app.models.user import User, UserRole

router = APIRouter(tags=["web"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/", response_class=HTMLResponse)
async def root():
    return RedirectResponse("/dashboard", status_code=302)


@router.get("/dashboard", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    today = date.today()
    is_manager = current_user.role.value in ("admin", "manager")
    is_rep = current_user.role == UserRole.field_rep

    # ── KPI Row 1 (all roles) ──────────────────────────────────────────────────
    total_outlets = db.query(func.count(Outlet.id)).filter(
        Outlet.status == OutletStatus.active
    ).scalar() or 0

    pending_approvals = db.query(func.count(Outlet.id)).filter(
        Outlet.status == OutletStatus.inactive
    ).scalar() or 0

    active_reps = db.query(func.count(User.id)).filter(
        User.role == UserRole.field_rep, User.is_active == True
    ).scalar() or 0

    total_products = db.query(func.count(Product.id)).filter(
        Product.is_active == True
    ).scalar() or 0

    # ── Orders today (role-scoped) ─────────────────────────────────────────────
    ord_q = db.query(func.count(Order.id)).filter(Order.order_date == today)
    if is_rep:
        ord_q = ord_q.filter(Order.user_id == current_user.id)
    orders_today = ord_q.scalar() or 0

    # ── Revenue today (confirmed/dispatched/delivered) ─────────────────────────
    active_statuses = [OrderStatus.confirmed, OrderStatus.dispatched, OrderStatus.delivered]
    rev_q = db.query(
        func.coalesce(
            func.sum(OrderItem.unit_price * OrderItem.quantity * (1 - OrderItem.discount_pct / 100)),
            0,
        )
    ).join(Order, Order.id == OrderItem.order_id).filter(
        Order.order_date == today,
        Order.status.in_(active_statuses),
    )
    if is_rep:
        rev_q = rev_q.filter(Order.user_id == current_user.id)
    revenue_today = round(float(rev_q.scalar() or 0), 2)

    # ── Visits today (role-scoped) ─────────────────────────────────────────────
    vis_q = db.query(func.count(VisitRecord.id)).filter(
        VisitRecord.visit_time >= f"{today} 00:00:00",
        VisitRecord.visit_time <= f"{today} 23:59:59",
    )
    if is_rep:
        vis_q = vis_q.filter(VisitRecord.user_id == current_user.id)
    visits_today = vis_q.scalar() or 0

    # ── Check-ins today (admin/manager only) ──────────────────────────────────
    checkins_today = 0
    pending_payments = 0
    open_mrs = 0
    unread_alerts = 0
    pending_expenses = 0

    if is_manager:
        checkins_today = db.query(func.count(Timesheet.id)).filter(
            Timesheet.work_date == today
        ).scalar() or 0

        pending_payments = db.query(func.count(Payment.id)).filter(
            Payment.status == PaymentStatus.collected
        ).scalar() or 0

        open_mrs = db.query(func.count(MaterialRequest.id)).filter(
            MaterialRequest.status.in_([MRStatus.submitted, MRStatus.acknowledged, MRStatus.in_progress])
        ).scalar() or 0

        unread_alerts = db.query(func.count(Alert.id)).filter(
            Alert.is_read == False
        ).scalar() or 0

        pending_expenses = db.query(func.count(Expense.id)).filter(
            Expense.status == ExpenseStatus.submitted
        ).scalar() or 0

    # ── Recent orders (last 6, role-scoped) ────────────────────────────────────
    rec_q = db.query(Order).order_by(Order.created_at.desc())
    if is_rep:
        rec_q = rec_q.filter(Order.user_id == current_user.id)
    recent_orders = rec_q.limit(6).all()

    # ── Integration sync status (check if any profile has credentials set) ──────
    profiles = db.query(CompanyProfile).filter(CompanyProfile.is_active == True).all()
    zap_configured = any(p.zap_base_url and p.zap_api_key_encrypted for p in profiles)
    cmms_configured = any(p.cmms_base_url and p.cmms_api_key_encrypted for p in profiles)
    connect_configured = any(p.connect_base_url and p.connect_api_key_encrypted for p in profiles)

    return templates.TemplateResponse(
        "dashboard/index.html",
        {
            "request": request,
            "current_user": current_user,
            "page_title": "Dashboard",
            # Row 1
            "total_outlets": total_outlets,
            "pending_approvals": pending_approvals,
            "active_reps": active_reps,
            "total_products": total_products,
            # Row 2
            "orders_today": orders_today,
            "revenue_today": revenue_today,
            "visits_today": visits_today,
            "checkins_today": checkins_today,
            # Manager extras
            "pending_payments": pending_payments,
            "open_mrs": open_mrs,
            "unread_alerts": unread_alerts,
            "pending_expenses": pending_expenses,
            # Recent activity
            "recent_orders": recent_orders,
            # Integration sync status
            "zap_configured": zap_configured,
            "cmms_configured": cmms_configured,
            "connect_configured": connect_configured,
        },
    )


@router.get("/coming-soon", response_class=HTMLResponse)
async def coming_soon(
    request: Request,
    current_user: User = Depends(require_web_auth),
    module: str = "",
    phase: str = "",
):
    return templates.TemplateResponse(
        "shared/coming_soon.html",
        {"request": request, "current_user": current_user, "module": module, "phase": phase},
    )
