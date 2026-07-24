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

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/channel-partners", tags=["channel-partners"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def channel_partner_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(LocalChannelPartner)
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
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("channel_partners/form.html", {
        "request": request,
        "current_user": current_user,
        "item": None,
        "beat_types": get_all_beat_types(db),
        "error": None,
    })


@router.post("/new")
async def channel_partner_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    partner_type: str = Form("Distributor"),
    beat_type: str = Form("GT"),
    contact_person: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    pincodes: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
):
    partner = LocalChannelPartner(
        name=name,
        partner_type=partner_type,
        beat_type=beat_type,
        contact_person=contact_person or None,
        mobile=mobile or None,
        email=email or None,
        address=address or None,
        erp_id=erp_id or None,
    )
    db.add(partner)
    db.commit()
    set_flash_success(request, f"Channel Partner '{name}' created.")
    return RedirectResponse("/channel-partners", status_code=302)


@router.get("/{cp_id}/edit", response_class=HTMLResponse)
async def channel_partner_edit(
    cp_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(LocalChannelPartner).filter(LocalChannelPartner.id == cp_id).first()
    if not item:
        set_flash_error(request, "Channel Partner not found.")
        return RedirectResponse("/channel-partners", status_code=302)

    return templates.TemplateResponse("channel_partners/form.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "beat_types": get_all_beat_types(db),
        "error": None,
    })


@router.post("/{cp_id}/edit")
async def channel_partner_update(
    cp_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    partner_type: str = Form("Distributor"),
    beat_type: str = Form("GT"),
    contact_person: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
    email: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    erp_id: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
):
    item = db.query(LocalChannelPartner).filter(LocalChannelPartner.id == cp_id).first()
    if not item:
        set_flash_error(request, "Channel Partner not found.")
        return RedirectResponse("/channel-partners", status_code=302)

    item.name = name
    item.partner_type = partner_type
    item.beat_type = beat_type
    item.contact_person = contact_person or None
    item.mobile = mobile or None
    item.email = email or None
    item.address = address or None
    item.erp_id = erp_id or None
    item.is_active = is_active == "on"

    db.commit()
    set_flash_success(request, f"Channel Partner '{name}' updated.")
    return RedirectResponse("/channel-partners", status_code=302)
