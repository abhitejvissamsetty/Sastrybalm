from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.beat import Beat
from app.models.user import User
from app.utils.timezone import ist_today

router = APIRouter(prefix="/api/v1", tags=["mobile-journey-plan"])


@router.get("/journey-plan")
async def get_journey_plan(
    target_user_id: Optional[int] = Query(None, description="Optional subordinate user ID for TMs"),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """
    Get journey plan / assigned beats & scheduled route for self or subordinate team member.
    """
    user_to_fetch = current_user
    if target_user_id and target_user_id != current_user.id:
        user_to_fetch = db.query(User).filter(User.id == target_user_id).first()
        if not user_to_fetch:
            raise HTTPException(status_code=404, detail="Requested user not found.")

    assigned_beats = []
    if hasattr(user_to_fetch, "positions"):
        for pos in user_to_fetch.positions:
            if getattr(pos, "is_active", True):
                for b in pos.beats:
                    if b.is_active:
                        assigned_beats.append({
                            "id": b.id,
                            "name": b.name,
                            "code": b.code,
                            "beat_type": b.beat_type.value,
                            "beat_grade": b.beat_grade.value if b.beat_grade else None,
                            "outlet_count": len(b.outlets) if b.outlets else 0,
                        })

    return {
        "user_id": user_to_fetch.id,
        "full_name": user_to_fetch.full_name,
        "role": user_to_fetch.role.value,
        "today_date": ist_today().isoformat(),
        "beats": assigned_beats,
    }
