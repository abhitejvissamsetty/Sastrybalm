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
    from app.utils.geography_scope import get_user_allowed_geography_ids
    from app.utils.timezone import ist_today
    today = ist_today()
    role_val = getattr(current_user.role, "value", str(current_user.role or ""))
    is_admin = role_val == "admin"
    is_tm = role_val == "territory_manager"
    is_rep = role_val == "field_rep"

    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)

    # ── 1. Outlets Scope ───────────────────────────────────────────────────────
    out_q = db.query(func.count(Outlet.id)).filter(Outlet.status == OutletStatus.active)
    if allowed_geo_ids is not None:
        out_q = out_q.filter(Outlet.territory_id.in_(allowed_geo_ids))
    total_outlets = out_q.scalar() or 0

    # ── 2. Pending Outlet Approvals Scope ─────────────────────────────────────
    appr_q = db.query(func.count(Outlet.id)).filter(Outlet.status == OutletStatus.inactive)
    if allowed_geo_ids is not None:
        appr_q = appr_q.filter(Outlet.territory_id.in_(allowed_geo_ids))
    pending_approvals = appr_q.scalar() or 0

    # ── 3. Field Workforce Scope ────────────────────────────────────────────────
    rep_q = db.query(func.count(User.id)).filter(User.role == UserRole.field_rep, User.is_active == True)
    if allowed_geo_ids is not None:
        rep_q = rep_q.filter(User.geography_id.in_(allowed_geo_ids))
    active_reps = rep_q.scalar() or 0

    # ── 4. Orders Today Scope ──────────────────────────────────────────────────
    ord_q = db.query(func.count(Order.id)).filter(Order.order_date == today)
    if is_rep:
        ord_q = ord_q.filter(Order.user_id == current_user.id)
    elif allowed_geo_ids is not None:
        rep_ids = [u.id for u in db.query(User.id).filter(User.geography_id.in_(allowed_geo_ids)).all()]
        ord_q = ord_q.filter(Order.user_id.in_(rep_ids)) if rep_ids else ord_q.filter(False)
    orders_today = ord_q.scalar() or 0

    # ── 5. Revenue Today Scope ─────────────────────────────────────────────────
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
    elif allowed_geo_ids is not None:
        rep_ids = [u.id for u in db.query(User.id).filter(User.geography_id.in_(allowed_geo_ids)).all()]
        rev_q = rev_q.filter(Order.user_id.in_(rep_ids)) if rep_ids else rev_q.filter(False)
    revenue_today = round(float(rev_q.scalar() or 0), 2)

    # ── 6. Visits Today Scope ──────────────────────────────────────────────────
    vis_q = db.query(func.count(VisitRecord.id)).filter(
        VisitRecord.visit_time >= f"{today} 00:00:00",
        VisitRecord.visit_time <= f"{today} 23:59:59",
    )
    if is_rep:
        vis_q = vis_q.filter(VisitRecord.user_id == current_user.id)
    elif allowed_geo_ids is not None:
        rep_ids = [u.id for u in db.query(User.id).filter(User.geography_id.in_(allowed_geo_ids)).all()]
        vis_q = vis_q.filter(VisitRecord.user_id.in_(rep_ids)) if rep_ids else vis_q.filter(False)
    visits_today = vis_q.scalar() or 0

    # ── 7. Check-ins Today Scope ───────────────────────────────────────────────
    ts_q = db.query(func.count(Timesheet.id)).filter(Timesheet.work_date == today)
    if is_rep:
        ts_q = ts_q.filter(Timesheet.user_id == current_user.id)
    elif allowed_geo_ids is not None:
        rep_ids = [u.id for u in db.query(User.id).filter(User.geography_id.in_(allowed_geo_ids)).all()]
        ts_q = ts_q.filter(Timesheet.user_id.in_(rep_ids)) if rep_ids else ts_q.filter(False)
    checkins_today = ts_q.scalar() or 0

    # ── 8. Operational Requests Scope (Expenses & Material Requests) ─────────
    exp_q = db.query(func.count(Expense.id)).filter(Expense.status == ExpenseStatus.submitted)
    mr_q = db.query(func.count(MaterialRequest.id)).filter(
        ~MaterialRequest.status.in_([MRStatus.completed, MRStatus.cancelled])
    )
    if allowed_geo_ids is not None:
        rep_ids = [u.id for u in db.query(User.id).filter(User.geography_id.in_(allowed_geo_ids)).all()]
        exp_q = exp_q.filter(Expense.user_id.in_(rep_ids)) if rep_ids else exp_q.filter(False)
        mr_q = mr_q.filter(MaterialRequest.user_id.in_(rep_ids)) if rep_ids else mr_q.filter(False)

    pending_expenses = exp_q.scalar() or 0
    open_mrs = mr_q.scalar() or 0

    # ── 9. Vendor & Asset Operational Data Metrics ─────────────────────────────
    from app.models.asset_capitalization import AssetCapitalization
    from app.models.procurement import WorkOrder, WorkOrderStatus, VendorQuotation, QuotationStatus

    active_assets = db.query(func.count(AssetCapitalization.id)).scalar() or 0

    open_work_orders = db.query(func.count(WorkOrder.id)).filter(
        WorkOrder.status == WorkOrderStatus.issued
    ).scalar() or 0

    pending_quotations = db.query(func.count(VendorQuotation.id)).filter(
        VendorQuotation.status == QuotationStatus.pending
    ).scalar() or 0

    # ── Recent orders (last 6, role-scoped) ────────────────────────────────────
    rec_q = db.query(Order).order_by(Order.created_at.desc())
    if is_rep:
        rec_q = rec_q.filter(Order.user_id == current_user.id)
    elif allowed_geo_ids is not None:
        rep_ids = [u.id for u in db.query(User.id).filter(User.geography_id.in_(allowed_geo_ids)).all()]
        rec_q = rec_q.filter(Order.user_id.in_(rep_ids)) if rep_ids else rec_q.filter(False)
    recent_orders = rec_q.limit(6).all()

    # ── Integration sync status ───────────────────────────────────────────────
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
            "total_outlets": total_outlets,
            "pending_approvals": pending_approvals,
            "active_reps": active_reps,
            "orders_today": orders_today,
            "revenue_today": revenue_today,
            "visits_today": visits_today,
            "checkins_today": checkins_today,
            "open_mrs": open_mrs,
            "pending_expenses": pending_expenses,
            "active_assets": active_assets,
            "open_work_orders": open_work_orders,
            "pending_quotations": pending_quotations,
            "recent_orders": recent_orders,
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
