from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.leave import Leave, LeaveStatus, LeaveType
from app.models.user import User

router = APIRouter(prefix="/api/v1", tags=["mobile-leaves"])


class LeaveApplySchema(BaseModel):
    leave_type: str
    start_date: date
    end_date: date
    duration: str = "full"
    half_day_session: Optional[str] = None
    reason: Optional[str] = None


@router.post("/leaves")
async def apply_leave(
    payload: LeaveApplySchema,
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Submit a leave request."""
    if payload.end_date < payload.start_date:
        raise HTTPException(status_code=400, detail="end_date cannot be earlier than start_date")
    if payload.start_date != payload.end_date:
        raise HTTPException(status_code=400, detail="Leave applications must be for a single day.")
    if payload.duration not in ("full", "half"):
        raise HTTPException(status_code=400, detail="duration must be 'full' or 'half'.")
    if payload.duration == "half" and payload.half_day_session not in ("first_half", "second_half"):
        raise HTTPException(status_code=400, detail="A valid half_day_session is required for half-day leave.")

    try:
        lt = LeaveType(payload.leave_type)
    except ValueError:
        lt = LeaveType.casual

    leave = Leave(
        user_id=current_user.id,
        leave_type=lt,
        start_date=payload.start_date,
        end_date=payload.end_date,
        duration=payload.duration,
        half_day_session=payload.half_day_session if payload.duration == "half" else None,
        reason=payload.reason,
        status=LeaveStatus.pending,
    )
    db.add(leave)
    db.commit()
    db.refresh(leave)

    return {
        "id": leave.id,
        "leave_type": leave.leave_type.value,
        "start_date": leave.start_date.isoformat(),
        "end_date": leave.end_date.isoformat(),
        "duration": leave.duration,
        "half_day_session": leave.half_day_session,
        "reason": leave.reason,
        "status": leave.status.value,
    }


@router.get("/leaves/my-leaves")
async def get_my_leaves(
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=20, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Fetch personal leave history."""
    query = db.query(Leave).filter(Leave.user_id == current_user.id)
    total = query.count()
    leaves = query.order_by(Leave.created_at.desc()).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "items": [
            {
                "id": l.id,
                "leave_type": l.leave_type.value,
                "start_date": l.start_date.isoformat(),
                "end_date": l.end_date.isoformat(),
                "duration": l.duration,
                "half_day_session": l.half_day_session,
                "reason": l.reason,
                "status": l.status.value,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leaves
        ]
    }
