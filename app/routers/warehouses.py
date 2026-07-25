import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.geography import Geography, GeoLevel
from app.models.warehouse import Warehouse
from app.models.product import Product
from app.models.user import User, UserRole
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/warehouses", tags=["warehouses"])
templates = Jinja2Templates(directory="app/templates")


def _get_regions(db: Session):
    return db.query(Geography).filter(Geography.level == GeoLevel.region, Geography.is_active == True).order_by(Geography.name).all()


@router.get("", response_class=HTMLResponse)
async def warehouse_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    """List all warehouses."""
    query = db.query(Warehouse)
    if q:
        query = query.filter(Warehouse.name.ilike(f"%{q}%") | Warehouse.code.ilike(f"%{q}%") | Warehouse.pincode.ilike(f"%{q}%"))
    query = query.order_by(Warehouse.name.asc())
    pagination = paginate(query, page)

    return templates.TemplateResponse("warehouses/list.html", {
        "request": request,
        "current_user": current_user,
        "pagination": pagination,
        "q": q,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def warehouse_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    return templates.TemplateResponse("warehouses/form.html", {
        "request": request,
        "current_user": current_user,
        "item": None,
        "error": None,
        "regions": _get_regions(db),
    })


@router.post("/new")
async def warehouse_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    pincode: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    geography_id: Optional[str] = Form(default=None),
):
    if db.query(Warehouse).filter(Warehouse.code == code.upper()).first():
        return templates.TemplateResponse("warehouses/form.html", {
            "request": request,
            "current_user": current_user,
            "item": None,
            "error": f"Warehouse code '{code.upper()}' already exists.",
            "regions": _get_regions(db),
        })

    wh = Warehouse(
        name=name,
        code=code.upper(),
        pincode=pincode or None,
        address=address or None,
        geography_id=int(geography_id) if geography_id else None,
    )
    db.add(wh)
    db.commit()
    set_flash_success(request, f"Warehouse '{name}' created.")
    return RedirectResponse("/warehouses", status_code=302)


@router.get("/{wh_id}/edit", response_class=HTMLResponse)
async def warehouse_edit(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if not item:
        set_flash_error(request, "Warehouse not found.")
        return RedirectResponse("/warehouses", status_code=302)

    return templates.TemplateResponse("warehouses/form.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "error": None,
        "regions": _get_regions(db),
    })


@router.post("/{wh_id}/edit")
async def warehouse_update(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    pincode: Optional[str] = Form(default=None),
    address: Optional[str] = Form(default=None),
    geography_id: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
):
    item = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if not item:
        set_flash_error(request, "Warehouse not found.")
        return RedirectResponse("/warehouses", status_code=302)

    if db.query(Warehouse).filter(Warehouse.code == code.upper(), Warehouse.id != wh_id).first():
        return templates.TemplateResponse("warehouses/form.html", {
            "request": request,
            "current_user": current_user,
            "item": item,
            "error": f"Warehouse code '{code.upper()}' already in use.",
            "regions": _get_regions(db),
        })

    item.name = name
    item.code = code.upper()
    item.pincode = pincode or None
    item.address = address or None
    item.geography_id = int(geography_id) if geography_id else None
    item.is_active = is_active == "on"

    db.commit()
    set_flash_success(request, f"Warehouse '{name}' updated.")
    return RedirectResponse("/warehouses", status_code=302)
