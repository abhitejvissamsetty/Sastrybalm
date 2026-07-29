from datetime import date
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.beat import Beat
from app.models.user import User
from app.utils.timezone import ist_today
from app.services.access_control import require_user_access

router = APIRouter(prefix="/api/v1", tags=["mobile-journey-plan"])


@router.get("/journey-plan")
async def get_journey_plan(
    target_user_id: Optional[int] = Query(None, description="Optional subordinate user ID for TMs"),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=50, ge=1, le=100),
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    """
    Get journey plan / assigned beats & scheduled route for self or subordinate team member.
    """
    user_to_fetch = current_user
    if target_user_id and target_user_id != current_user.id:
        user_to_fetch = require_user_access(db, current_user, target_user_id)

    assigned_beat_ids = set()
    if hasattr(user_to_fetch, "positions"):
        for pos in user_to_fetch.positions:
            if getattr(pos, "is_active", True):
                for b in pos.beats:
                    if b.is_active:
                        assigned_beat_ids.add(b.id)

    beat_query = db.query(Beat).filter(
        Beat.id.in_(assigned_beat_ids or {-1}), Beat.is_active == True
    )
    total = beat_query.count()
    beats = beat_query.order_by(Beat.name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()
    assigned_beats = [
        {
                            "id": b.id,
                            "name": b.name,
                            "code": b.code,
                            "beat_type": b.beat_type.value,
                            "beat_grade": b.beat_grade.value if b.beat_grade else None,
                            "outlet_count": len(b.outlets) if b.outlets else 0,
        }
        for b in beats
    ]

    return {
        "user_id": user_to_fetch.id,
        "full_name": user_to_fetch.full_name,
        "role": user_to_fetch.role.value,
        "today_date": ist_today().isoformat(),
        "page": page,
        "per_page": per_page,
        "total": total,
        "beats": assigned_beats,
    }
