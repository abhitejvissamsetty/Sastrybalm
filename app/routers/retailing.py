from typing import Optional
from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, selectinload

from app.dependencies import get_db, require_web_auth
from app.models.beat import Beat
from app.models.outlet import Outlet, OutletStatus
from app.models.position import Position, PositionLevel
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error
from app.utils.geography_scope import get_user_allowed_geography_ids
from app.utils.pagination import paginate
from app.services.access_control import require_beat_access, scope_beat_query

router = APIRouter(prefix="", tags=["retailing"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/api/retailing/beats", response_class=JSONResponse)
async def api_retailing_beats(
    request: Request,
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
    per_page: int = Query(default=100, ge=1, le=100),
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    """
    Returns active beats with L1 position mappings and attached user info.
    Accessible to L1, L2, L3, L4 users (scoped by geography/position).
    """
    query = db.query(Beat).options(
        selectinload(Beat.positions).selectinload(Position.users)
    ).filter(Beat.is_active == True)

    query = scope_beat_query(query, current_user, db)

    if q:
        query = query.filter(
            Beat.name.ilike(f"%{q}%") | Beat.code.ilike(f"%{q}%")
        )
    total = query.count()
    beats = query.order_by(Beat.name).offset(
        (page - 1) * per_page
    ).limit(per_page).all()

    result = []
    for b in beats:
        l1_positions = [p for p in b.positions if p.is_active and p.level_code == "L1"]
        # Fallback to any active position if no L1 explicitly tagged
        target_positions = l1_positions if l1_positions else [p for p in b.positions if p.is_active]

        l1_info_list = []
        if target_positions:
            for pos in target_positions:
                active_users = [u.full_name for u in pos.users if u.is_active]
                user_str = ", ".join(active_users) if active_users else "Vacant"
                l1_info_list.append(f"Position: {pos.name} ({pos.code}) • User: {user_str}")
            l1_display = " | ".join(l1_info_list)
        else:
            l1_display = "Position: L1 General • User: Unassigned"

        result.append({
            "id": b.id,
            "name": b.name,
            "code": b.code,
            "beat_type": b.beat_type.value if hasattr(b.beat_type, "value") else str(b.beat_type),
            "outlet_count": b.active_outlet_count,
            "l1_display": l1_display,
        })

    return {"page": page, "per_page": per_page, "total": total, "beats": result}


@router.get("/retailing/beat/{beat_id}", response_class=HTMLResponse)
async def retailing_beat_view(
    beat_id: int,
    request: Request,
    page: int = Query(default=1, ge=1),
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    """
    Beat Retailing View - Excludes footer menu.
    Displays all active outlets with Outlet Name, Code/ID, and Phone Number.
    Includes FABs for Search and New Outlet (New Outlet enabled for L1 position).
    """
    beat = require_beat_access(db, current_user, beat_id, active_only=True)

    pagination = paginate(db.query(Outlet).filter(
        Outlet.beat_id == beat_id,
        Outlet.status == OutletStatus.active
    ).order_by(Outlet.name), page)
    outlets = pagination.items

    # Determine if current user holds an L1 position or Field Rep role
    user_positions = getattr(current_user, "positions", [])
    has_l1_position = any(p.level_code == "L1" for p in user_positions if p.is_active) or current_user.role == UserRole.field_rep

    return templates.TemplateResponse("beats/retailing_view.html", {
        "request": request,
        "current_user": current_user,
        "beat": beat,
        "outlets": outlets,
        "pagination": pagination,
        "has_l1_position": has_l1_position,
        **get_flash(request),
    })
