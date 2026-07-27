"""
Unified Approvals Hub — Shows pending items across all modules.
"""
from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.attendance import Attendance, ApprovalStatus
from app.models.expense import Expense, ExpenseStatus
from app.models.material_request import MaterialRequest, MRStatus
from app.models.outlet import Outlet, OutletStatus
from app.models.payment_submission import PaymentSubmission, SubmissionStatus
from app.models.timesheet import Timesheet, TimesheetApproval
from app.models.user import User, UserRole
from app.utils.flash import get_flash

router = APIRouter(prefix="/approvals", tags=["approvals"])
templates = Jinja2Templates(directory="app/templates")

_ADMIN_MANAGER = require_web_roles(UserRole.admin, UserRole.territory_manager)


from fastapi import HTTPException
from app.utils.geography_scope import get_user_allowed_geography_ids
from app.models.position import Position, PositionLevel
from app.models.geography import GeoLevel
from app.models.auto_flag import AutoFlag, FlagStatus


def _check_approval_hub_permissions(user: User, db: Session):
    """
    Approval Hub is available for users with Position level > L2 (L3, L4, L5)
    and user Geography scope >= Region (Region, Zone), or Admin.
    """
    if user.role == UserRole.admin:
        return True
    
    # Check active positions level
    pos_levels = [p.level.value for p in user.positions if p.is_active] if user.positions else []
    if not any(lvl in ["L3", "L4", "L5"] for lvl in pos_levels):
        raise HTTPException(status_code=403, detail="Approval Hub requires Position level > L2 (L3, L4, L5).")

    allowed_geo_ids = get_user_allowed_geography_ids(user, db)
    if not allowed_geo_ids:
        raise HTTPException(status_code=403, detail="Approval Hub requires Geography scope >= Region.")
    return True


@router.get("", response_class=HTMLResponse)
async def approvals_hub(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
):
    """Central hub showing pending counts across all approval queues scoped by user position & geography."""
    _check_approval_hub_permissions(current_user, db)

    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)

    # Attendance approvals
    att_q = db.query(func.count(Attendance.id)).filter(Attendance.approval_status == ApprovalStatus.pending)
    if allowed_geo_ids is not None:
        att_q = att_q.join(User, Attendance.user_id == User.id).filter(User.geography_id.in_(allowed_geo_ids))
    pending_attendance = att_q.scalar() or 0

    # Timesheet approvals
    ts_q = db.query(func.count(Timesheet.id)).filter(Timesheet.approval_status == TimesheetApproval.pending)
    if allowed_geo_ids is not None:
        ts_q = ts_q.join(User, Timesheet.user_id == User.id).filter(User.geography_id.in_(allowed_geo_ids))
    pending_timesheets = ts_q.scalar() or 0

    # Payment submission approvals
    ps_q = db.query(func.count(PaymentSubmission.id)).filter(PaymentSubmission.status == SubmissionStatus.pending)
    if allowed_geo_ids is not None:
        ps_q = ps_q.join(User, PaymentSubmission.user_id == User.id).filter(User.geography_id.in_(allowed_geo_ids))
    pending_submissions = ps_q.scalar() or 0

    # Expense approvals
    exp_q = db.query(func.count(Expense.id)).filter(Expense.status == ExpenseStatus.submitted)
    if allowed_geo_ids is not None:
        exp_q = exp_q.join(User, Expense.user_id == User.id).filter(User.geography_id.in_(allowed_geo_ids))
    pending_expenses = exp_q.scalar() or 0

    # Material request approvals
    mr_q = db.query(func.count(MaterialRequest.id)).filter(MaterialRequest.status.in_([MRStatus.submitted, MRStatus.acknowledged]))
    if allowed_geo_ids is not None:
        mr_q = mr_q.join(User, MaterialRequest.user_id == User.id).filter(User.geography_id.in_(allowed_geo_ids))
    pending_mrs = mr_q.scalar() or 0

    # Master Data / Outlet Edit approvals
    md_q = db.query(func.count(AutoFlag.id)).filter(
        AutoFlag.entity_type == "outlet_edit_approval",
        AutoFlag.status == FlagStatus.open
    )
    if allowed_geo_ids is not None:
        md_q = md_q.join(User, AutoFlag.user_id == User.id).filter(User.geography_id.in_(allowed_geo_ids))
    pending_master_edits = md_q.scalar() or 0

    queues = [
        {
            "name": "Outlet & Master Data Edits",
            "icon": "🏬",
            "count": pending_master_edits,
            "url": "/flags?entity_type=outlet_edit_approval",
            "description": "Master data and outlet modification approval requests",
        },
        {
            "name": "Attendance",
            "icon": "📋",
            "count": pending_attendance,
            "url": "/attendance?approval=pending",
            "description": "Pending daily attendance approvals",
        },
        {
            "name": "Timesheets",
            "icon": "⏱️",
            "count": pending_timesheets,
            "url": "/tracking/timesheets",
            "description": "Timesheet entries awaiting approval",
        },
        {
            "name": "Payment Submissions",
            "icon": "💰",
            "count": pending_submissions,
            "url": "/payment-submissions?status=pending",
            "description": "Rep payment batches awaiting verification",
        },
        {
            "name": "Expenses",
            "icon": "🧾",
            "count": pending_expenses,
            "url": "/expenses",
            "description": "Submitted expense claims pending approval",
        },
        {
            "name": "Material Requests",
            "icon": "🔧",
            "count": pending_mrs,
            "url": "/material-requests",
            "description": "CMMS material requests in progress",
        },
    ]

    total_pending = sum(q["count"] for q in queues)

    return templates.TemplateResponse("approvals/hub.html", {
        "request": request, "current_user": current_user,
        "queues": queues, "total_pending": total_pending,
        **get_flash(request),
    })
