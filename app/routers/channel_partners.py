import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.local_distribution import LocalChannelPartner
from app.models.user import User, UserRole
from app.utils.beat_types import get_all_beat_types
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate
from app.services.access_control import (
    require_channel_partner_access,
    scope_channel_partner_query,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/master-data/channel-partners", tags=["channel-partners"])
templates = Jinja2Templates(directory="app/templates")





import json
from app.models.geography import Geography, GeoLevel


from app.utils.geography_scope import get_user_allowed_geography_ids


def _get_tm_allowed_geo_ids(db: Session, user: User) -> list[int]:
    res = get_user_allowed_geography_ids(user, db)
    return res if res is not None else []


def _cp_form_context(db: Session, user: Optional[User] = None):
    geo_query = db.query(Geography).filter(
        Geography.is_active == True,
        Geography.level.in_([GeoLevel.territory, GeoLevel.region])
    )
    if user and user.role == UserRole.territory_manager:
        allowed_ids = _get_tm_allowed_geo_ids(db, user)
        geo_query = geo_query.filter(Geography.id.in_(allowed_ids))

    geographies = geo_query.order_by(Geography.level, Geography.name).all()
    beat_types = get_all_beat_types(db)
    return {"geographies": geographies, "beat_types": beat_types}


@router.get("", response_class=HTMLResponse)
async def channel_partner_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = scope_channel_partner_query(
        db.query(LocalChannelPartner), current_user, db
    )

    if q:
        query = query.filter(
            LocalChannelPartner.name.ilike(f"%{q}%") |
            LocalChannelPartner.erp_id.ilike(f"%{q}%") |
            LocalChannelPartner.mobile.ilike(f"%{q}%")
        )
    query = query.order_by(LocalChannelPartner.name.asc())
    pagination = paginate(query, page)

    return templates.TemplateResponse("channel_partners/list.html", {
        "request": request,
        "current_user": current_user,
        "pagination": pagination,
        "q": q,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def channel_partner_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("channel_partners/form.html", {
        "request": request,
        "current_user": current_user,
        "item": None,
        "error": None,
        **_cp_form_context(db, current_user),
    })


@router.post("/new")
async def channel_partner_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    partner_type: str = Form("Distributor"),
    geography_id: Optional[str] = Form(default=None),
    sales_channels: list[str] = Form(default=[]),
    contact_person: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    pincodes: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
    notification_preference: str = Form("none"),
    notification_channel: str = Form("in_app"),
):
    form_data = await request.form()
    raw_channels = form_data.getlist("sales_channels") or sales_channels
    selected_channels = [c for c in raw_channels if c and c.strip()]

    err = None
    if not selected_channels:
        err = "Selecting at least one Sales Channel is mandatory."

    geo_id_int = int(geography_id) if geography_id and str(geography_id).isdigit() else None
    if not err and not geo_id_int:
        err = "Selecting a Geography (Territory or Region) is mandatory."
    elif not err and geo_id_int:
        if current_user.role == UserRole.territory_manager:
            allowed_ids = _get_tm_allowed_geo_ids(db, current_user)
            if geo_id_int not in allowed_ids:
                err = "You can only assign Channel Partners to geographies within your assigned Region."

        if not err:
            geo_node = db.query(Geography).filter(Geography.id == geo_id_int, Geography.is_active == True).first()
            if not geo_node or geo_node.level not in [GeoLevel.territory, GeoLevel.region]:
                err = "Geography scope must be a Territory or Region."

    if err:
        return templates.TemplateResponse("channel_partners/form.html", {
            "request": request,
            "current_user": current_user,
            "item": None,
            "error": err,
            **_cp_form_context(db, current_user),
        })

    import uuid
    partner_code = f"CP-{uuid.uuid4().hex[:6].upper()}"
    partner = LocalChannelPartner(
        code=partner_code,
        name=name,
        partner_type=partner_type,
        beat_type=selected_channels[0] if selected_channels else "GT",
        sales_channels=json.dumps(selected_channels),
        geography_id=geo_id_int,
        territory_name=geo_node.name if geo_node else None,
        contact_person=contact_person or None,
        mobile=mobile or None,
        email=email or None,
        address=address or None,
        erp_id=erp_id or None,
        notification_preference=notification_preference,
        notification_channel=notification_channel,
    )
    db.add(partner)
    db.commit()
    set_flash_success(request, f"Channel Partner '{name}' created.")
    return RedirectResponse("/master-data/channel-partners", status_code=302)


@router.get("/{cp_id}/edit", response_class=HTMLResponse)
async def channel_partner_edit(
    cp_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = require_channel_partner_access(db, current_user, cp_id)

    return templates.TemplateResponse("channel_partners/form.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "error": None,
        **_cp_form_context(db, current_user),
    })


@router.post("/{cp_id}/edit")
async def channel_partner_update(
    cp_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    partner_type: str = Form("Distributor"),
    geography_id: Optional[str] = Form(default=None),
    sales_channels: list[str] = Form(default=[]),
    contact_person: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
    notification_preference: str = Form("none"),
    notification_channel: str = Form("in_app"),
    is_active: Optional[str] = Form(default=None),
):
    item = require_channel_partner_access(db, current_user, cp_id)

    form_data = await request.form()
    raw_channels = form_data.getlist("sales_channels") or sales_channels
    selected_channels = [c for c in raw_channels if c and c.strip()]

    err = None
    if not selected_channels:
        err = "Selecting at least one Sales Channel is mandatory."

    geo_id_int = int(geography_id) if geography_id and str(geography_id).isdigit() else None
    if not err and not geo_id_int:
        err = "Selecting a Geography (Territory or Region) is mandatory."
    elif not err and geo_id_int:
        if current_user.role == UserRole.territory_manager:
            allowed_ids = _get_tm_allowed_geo_ids(db, current_user)
            if geo_id_int not in allowed_ids:
                err = "You can only assign Channel Partners to geographies within your assigned Region."

        if not err:
            geo_node = db.query(Geography).filter(Geography.id == geo_id_int, Geography.is_active == True).first()
            if not geo_node or geo_node.level not in [GeoLevel.territory, GeoLevel.region]:
                err = "Geography scope must be a Territory or Region."

    if err:
        return templates.TemplateResponse("channel_partners/form.html", {
            "request": request,
            "current_user": current_user,
            "item": item,
            "error": err,
            **_cp_form_context(db, current_user),
        })

    item.name = name
    item.partner_type = partner_type
    item.beat_type = selected_channels[0] if selected_channels else "GT"
    item.sales_channels = json.dumps(selected_channels)
    item.geography_id = geo_id_int
    item.territory_name = geo_node.name if geo_node else item.territory_name
    item.contact_person = contact_person or None
    item.mobile = mobile or None
    item.email = email or None
    item.address = address or None
    item.erp_id = erp_id or None
    item.notification_preference = notification_preference
    item.notification_channel = notification_channel
    if is_active is not None:
        item.is_active = is_active == "on"

    db.commit()
    set_flash_success(request, f"Channel Partner '{name}' updated.")
    return RedirectResponse("/master-data/channel-partners", status_code=302)


@router.post("/{cp_id}/deactivate")
async def channel_partner_deactivate(
    cp_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = require_channel_partner_access(db, current_user, cp_id)

    item.is_active = False
    db.commit()
    set_flash_success(request, f"Channel Partner '{item.name}' deactivated.")
    return RedirectResponse("/master-data/channel-partners", status_code=302)


@router.post("/{cp_id}/activate")
async def channel_partner_activate(
    cp_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = require_channel_partner_access(db, current_user, cp_id)

    item.is_active = True
    db.commit()
    set_flash_success(request, f"Channel Partner '{item.name}' activated.")
    return RedirectResponse("/master-data/channel-partners", status_code=302)


from fastapi.responses import Response
from app.services.channel_partner_notification import generate_channel_partner_daily_orders_csv


@router.get("/{cp_id}/export-daily-orders-csv")
async def export_channel_partner_daily_orders_csv(
    cp_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = require_channel_partner_access(db, current_user, cp_id)

    csv_data = generate_channel_partner_daily_orders_csv(db, item)
    filename = f"channel_partner_{item.code or item.id}_daily_orders.csv"
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
