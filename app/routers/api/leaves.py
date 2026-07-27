from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
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

    try:
        lt = LeaveType(payload.leave_type)
    except ValueError:
        lt = LeaveType.casual

    leave = Leave(
        user_id=current_user.id,
        leave_type=lt,
        start_date=payload.start_date,
        end_date=payload.end_date,
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
        "reason": leave.reason,
        "status": leave.status.value,
    }


@router.get("/leaves/my-leaves")
async def get_my_leaves(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """Fetch personal leave history."""
    leaves = db.query(Leave).filter(Leave.user_id == current_user.id).order_by(Leave.created_at.desc()).all()
    return {
        "items": [
            {
                "id": l.id,
                "leave_type": l.leave_type.value,
                "start_date": l.start_date.isoformat(),
                "end_date": l.end_date.isoformat(),
                "reason": l.reason,
                "status": l.status.value,
                "created_at": l.created_at.isoformat() if l.created_at else None,
            }
            for l in leaves
        ]
    }
