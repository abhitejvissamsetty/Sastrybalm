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


@router.get("", response_class=HTMLResponse)
async def approvals_hub(
    request: Request,
    current_user: User = Depends(_ADMIN_MANAGER),
    db: Session = Depends(get_db),
):
    """Central hub showing pending counts across all approval queues."""

    # Attendance approvals
    pending_attendance = db.query(func.count(Attendance.id)).filter(
        Attendance.approval_status == ApprovalStatus.pending,
    ).scalar() or 0

    # Timesheet approvals
    pending_timesheets = db.query(func.count(Timesheet.id)).filter(
        Timesheet.approval_status == TimesheetApproval.pending,
    ).scalar() or 0

    # Payment submission approvals
    pending_submissions = db.query(func.count(PaymentSubmission.id)).filter(
        PaymentSubmission.status == SubmissionStatus.pending,
    ).scalar() or 0

    # Expense approvals
    pending_expenses = db.query(func.count(Expense.id)).filter(
        Expense.status == ExpenseStatus.submitted,
    ).scalar() or 0

    # Material request approvals (submitted/acknowledged)
    pending_mrs = db.query(func.count(MaterialRequest.id)).filter(
        MaterialRequest.status.in_([MRStatus.submitted, MRStatus.acknowledged]),
    ).scalar() or 0

    queues = [
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
