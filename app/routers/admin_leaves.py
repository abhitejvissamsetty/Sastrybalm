from typing import Optional
from fastapi import APIRouter, Depends, Form, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload
from datetime import datetime

from app.dependencies import get_db, require_web_auth
from app.models.leave import Leave, LeaveStatus
from app.models.user import User
from app.models.position import Position, PositionLevel
from app.utils.pagination import paginate
from app.services.access_control import (
    require_leave_access,
    scope_employee_record_query,
)

router = APIRouter(prefix="/leaves", tags=["admin-leaves"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def list_leaves(
    request: Request,
    status_filter: Optional[str] = None,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    query = scope_employee_record_query(
        db.query(Leave).options(
            joinedload(Leave.user).joinedload(User.positions)
        ), Leave, current_user, db
    )
    if status_filter:
        query = query.filter(Leave.status == status_filter)
    if current_user.level == "L3":
        query = (
            query.join(User, Leave.user_id == User.id)
            .join(User.positions)
            .filter(
                Position.is_active == True,
                Position.level.in_([PositionLevel.L1, PositionLevel.L2]),
            )
            .distinct()
        )
    elif current_user.level in ("L1", "L2"):
        query = query.filter(Leave.id == -1)
    pagination = paginate(query.order_by(Leave.created_at.desc()), page)
    leaves = pagination.items

    # Annotate leaves with approval authorization for current user
    for l in leaves:
        setattr(l, "can_approve", current_user.can_approve_leave_for(l.user, db))

    return templates.TemplateResponse(
        "leaves/index.html",
        {
            "request": request,
            "current_user": current_user,
            "leaves": leaves,
            "pagination": pagination,
            "status_filter": status_filter,
            "active_nav": "leaves",
        },
    )


@router.post("/{leave_id}/approve")
async def approve_leave(
    leave_id: int,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    leave = require_leave_access(db, current_user, leave_id)
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=409, detail="Leave is not awaiting approval.")

    if not current_user.can_approve_leave_for(leave.user, db):
        applicant_lvl = leave.user.level if leave.user else "L1"
        raise HTTPException(
            status_code=403,
            detail=f"Permission Denied: Your level ({current_user.level}) cannot approve {applicant_lvl} leaves. L1/L2 leaves require L3/L4 approval. L3 leaves require L4 approval ONLY."
        )

    leave.status = LeaveStatus.approved
    leave.approved_by_id = current_user.id
    leave.approved_at = datetime.utcnow()
    db.commit()

    return RedirectResponse(url="/leaves", status_code=302)


@router.post("/{leave_id}/reject")
async def reject_leave(
    leave_id: int,
    rejection_reason: str = Form(default=""),
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    leave = require_leave_access(db, current_user, leave_id)
    if leave.status != LeaveStatus.pending:
        raise HTTPException(status_code=409, detail="Leave is not awaiting review.")
    if not rejection_reason.strip():
        raise HTTPException(status_code=400, detail="Rejection reason is required.")

    if not current_user.can_approve_leave_for(leave.user, db):
        applicant_lvl = leave.user.level if leave.user else "L1"
        raise HTTPException(
            status_code=403,
            detail=f"Permission Denied: Your level ({current_user.level}) cannot reject {applicant_lvl} leaves. L1/L2 leaves require L3/L4 approval. L3 leaves require L4 approval ONLY."
        )

    leave.status = LeaveStatus.rejected
    leave.approved_by_id = current_user.id
    leave.rejection_reason = rejection_reason.strip()
    db.commit()

    return RedirectResponse(url="/leaves", status_code=302)
