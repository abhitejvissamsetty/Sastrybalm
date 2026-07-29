from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles, require_restricted_module_web_access
from app.models.beat import Beat, BeatType, BeatGrade, parse_beat_type, parse_beat_grade
from app.models.geography import Geography, GeoLevel
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

from app.utils.beat_types import get_all_beat_types
from app.services.access_control import (
    build_access_scope,
    require_beat_access,
    require_channel_partner_access,
    scope_beat_query,
)

router = APIRouter(prefix="/master-data/beats", tags=["beats"])
templates = Jinja2Templates(directory="app/templates")


from app.utils.geography_scope import get_user_allowed_geography_ids


@router.get("", response_class=HTMLResponse)
async def beat_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    beat_type: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    from sqlalchemy.orm import selectinload
    from app.models.position import Position

    query = scope_beat_query(
        db.query(Beat).options(selectinload(Beat.positions)),
        current_user,
        db,
    )

    if q:
        query = query.outerjoin(Beat.positions).filter(
            Beat.name.ilike(f"%{q}%") | Beat.code.ilike(f"%{q}%") | Position.name.ilike(f"%{q}%") | Position.code.ilike(f"%{q}%")
        ).distinct()
    if beat_type:
        query = query.filter(Beat.beat_type == beat_type)
    query = query.order_by(Beat.name)
    pagination = paginate(query, page)
    return templates.TemplateResponse("beats/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "beat_type": beat_type,
        "beat_types": get_all_beat_types(db), "BeatType": BeatType, **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def beat_new(
    request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
):
    from app.models.local_distribution import LocalChannelPartner
    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)

    terr_query = db.query(Geography).filter(
        Geography.level == GeoLevel.territory, Geography.is_active == True
    )
    cp_query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)

    if allowed_geo_ids is not None:
        terr_query = terr_query.filter(Geography.id.in_(allowed_geo_ids))
        cp_query = cp_query.filter(LocalChannelPartner.geography_id.in_(allowed_geo_ids))

    territories = terr_query.order_by(Geography.name).all()
    channel_partners = cp_query.order_by(LocalChannelPartner.name).all()

    return templates.TemplateResponse("beats/form.html", {
        "request": request, "current_user": current_user,
        "item": None, "territories": territories, "channel_partners": channel_partners,
        "attached_ids": [], "beat_types": get_all_beat_types(db), "BeatType": BeatType, "BeatGrade": BeatGrade, "error": None,
    })


@router.post("/new")
async def beat_create(
    request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    beat_type: str = Form(...),
    description: Optional[str] = Form(default=None),
    pincodes: Optional[str] = Form(default=None),
    beat_grade: Optional[str] = Form(default=None),
    territory_id: Optional[str] = Form(default=None),
    channel_partner_ids: list[str] = Form(default=[]),
    erp_id: Optional[str] = Form(default=None),
):
    from app.models.local_distribution import LocalChannelPartner
    from app.models.beat_channel_partner import BeatChannelPartner

    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)

    terr_query = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True)
    cp_query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)
    if allowed_geo_ids is not None:
        terr_query = terr_query.filter(Geography.id.in_(allowed_geo_ids))
        cp_query = cp_query.filter(LocalChannelPartner.geography_id.in_(allowed_geo_ids))

    if db.query(Beat).filter(Beat.code == code.upper()).first():
        territories = terr_query.order_by(Geography.name).all()
        channel_partners = cp_query.order_by(LocalChannelPartner.name).all()
        return templates.TemplateResponse("beats/form.html", {
            "request": request, "current_user": current_user,
            "item": None, "territories": territories, "channel_partners": channel_partners,
            "attached_ids": [], "beat_types": get_all_beat_types(db), "BeatType": BeatType, "BeatGrade": BeatGrade,
            "error": f"Code '{code.upper()}' already exists.",
        })
    
    assigned_terr_id = int(territory_id) if territory_id else None
    if allowed_geo_ids is not None:
        if assigned_terr_id and assigned_terr_id not in allowed_geo_ids:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Geography not found.")

    beat = Beat(
        name=name, code=code.upper(), beat_type=parse_beat_type(beat_type),
        description=description or None, pincodes=pincodes or None,
        beat_grade=parse_beat_grade(beat_grade),
        territory_id=assigned_terr_id,
        erp_id=erp_id or None,
    )
    db.add(beat)
    db.flush()

    if channel_partner_ids:
        for c_id in channel_partner_ids:
            partner = require_channel_partner_access(db, current_user, int(c_id))
            db.add(BeatChannelPartner(
                beat_id=beat.id, channel_partner_id=partner.id
            ))

    db.commit()
    set_flash_success(request, f"Beat '{name}' created.")
    return RedirectResponse("/master-data/beats", status_code=302)


@router.get("/{beat_id}/edit", response_class=HTMLResponse)
async def beat_edit(
    beat_id: int, request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
):
    from app.models.local_distribution import LocalChannelPartner
    from app.models.beat_channel_partner import BeatChannelPartner

    item = require_beat_access(db, current_user, beat_id, active_only=True)
    allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)

    terr_query = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True)
    cp_query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)
    if allowed_geo_ids is not None:
        terr_query = terr_query.filter(Geography.id.in_(allowed_geo_ids))
        cp_query = cp_query.filter(LocalChannelPartner.geography_id.in_(allowed_geo_ids))

    territories = terr_query.order_by(Geography.name).all()
    channel_partners = cp_query.order_by(LocalChannelPartner.name).all()
    attached_ids = [bcp.channel_partner_id for bcp in db.query(BeatChannelPartner).filter(BeatChannelPartner.beat_id == beat_id).all()]

    return templates.TemplateResponse("beats/form.html", {
        "request": request, "current_user": current_user,
        "item": item, "territories": territories, "channel_partners": channel_partners,
        "attached_ids": attached_ids, "beat_types": get_all_beat_types(db), "BeatType": BeatType, "BeatGrade": BeatGrade, "error": None,
    })


@router.post("/{beat_id}/edit")
async def beat_update(
    beat_id: int, request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    beat_type: str = Form(...),
    description: Optional[str] = Form(default=None),
    pincodes: Optional[str] = Form(default=None),
    beat_grade: Optional[str] = Form(default=None),
    territory_id: Optional[str] = Form(default=None),
    channel_partner_ids: list[str] = Form(default=[]),
    erp_id: Optional[str] = Form(default=None),
):
    from app.models.local_distribution import LocalChannelPartner
    from app.models.beat_channel_partner import BeatChannelPartner

    item = require_beat_access(db, current_user, beat_id, active_only=True)
    if db.query(Beat).filter(Beat.code == code.upper(), Beat.id != beat_id).first():
        cp_query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)
        allowed_geo_ids = get_user_allowed_geography_ids(current_user, db)
        if allowed_geo_ids is not None:
            cp_query = cp_query.filter(LocalChannelPartner.geography_id.in_(allowed_geo_ids))
        channel_partners = cp_query.order_by(LocalChannelPartner.name).all()
        attached_ids = [bcp.channel_partner_id for bcp in db.query(BeatChannelPartner).filter(BeatChannelPartner.beat_id == beat_id).all()]
        terr_query = db.query(Geography).filter(Geography.level == GeoLevel.territory, Geography.is_active == True)
        if allowed_geo_ids is not None:
            terr_query = terr_query.filter(Geography.id.in_(allowed_geo_ids))
        territories = terr_query.order_by(Geography.name).all()
        return templates.TemplateResponse("beats/form.html", {
            "request": request, "current_user": current_user,
            "item": item, "territories": territories, "channel_partners": channel_partners,
            "attached_ids": attached_ids, "beat_types": get_all_beat_types(db), "BeatType": BeatType, "BeatGrade": BeatGrade,
            "error": f"Code '{code.upper()}' already in use.",
        })
    item.name = name
    item.code = code.upper()
    item.beat_type = parse_beat_type(beat_type)
    item.description = description or None
    item.pincodes = pincodes or None
    item.beat_grade = parse_beat_grade(beat_grade)
    requested_territory_id = int(territory_id) if territory_id else None
    access_scope = build_access_scope(current_user, db)
    if (
        requested_territory_id
        and not access_scope.allows_geography(requested_territory_id)
    ):
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Geography not found.")
    item.territory_id = requested_territory_id
    item.erp_id = erp_id or None

    db.query(BeatChannelPartner).filter(BeatChannelPartner.beat_id == beat_id).delete()
    if channel_partner_ids:
        for c_id in channel_partner_ids:
            partner = require_channel_partner_access(db, current_user, int(c_id))
            db.add(BeatChannelPartner(
                beat_id=beat_id, channel_partner_id=partner.id
            ))

    db.commit()
    set_flash_success(request, f"Beat '{name}' updated.")
    return RedirectResponse("/master-data/beats", status_code=302)


@router.post("/{beat_id}/activate")
async def beat_activate(
    beat_id: int, request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
):
    item = require_beat_access(db, current_user, beat_id)
    item.is_active = True
    db.commit()
    set_flash_success(request, f"'{item.name}' activated.")
    return RedirectResponse("/master-data/beats", status_code=302)


@router.post("/{beat_id}/delete")
async def beat_delete(
    beat_id: int, request: Request,
    current_user: User = Depends(require_restricted_module_web_access),
    db: Session = Depends(get_db),
):
    item = require_beat_access(db, current_user, beat_id)
    if item.active_outlet_count > 0:
        set_flash_error(request, f"Cannot deactivate '{item.name}' because it has active outlets.")
        return RedirectResponse("/master-data/beats", status_code=302)
    if any(p.is_active for p in item.positions):
        set_flash_error(request, f"Cannot deactivate '{item.name}' because it is attached to active positions.")
        return RedirectResponse("/master-data/beats", status_code=302)

    item.is_active = False
    db.commit()
    set_flash_success(request, f"'{item.name}' deactivated.")
    return RedirectResponse("/beats", status_code=302)
