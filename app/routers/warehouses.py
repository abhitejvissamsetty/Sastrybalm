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

router = APIRouter(prefix="/catalogue/warehouses", tags=["warehouses"])
templates = Jinja2Templates(directory="app/templates")


def _get_regions(db: Session):
    return db.query(Geography).filter(Geography.level == GeoLevel.region, Geography.is_active == True).order_by(Geography.name).all()


from app.utils.geography_scope import get_user_allowed_warehouse_ids

@router.get("", response_class=HTMLResponse)
async def warehouse_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    """List warehouses scoped to user's assigned geography."""
    query = db.query(Warehouse)
    allowed_wh_ids = get_user_allowed_warehouse_ids(current_user, db)
    if allowed_wh_ids is not None:
        query = query.filter(Warehouse.id.in_(allowed_wh_ids))

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
    return RedirectResponse("/catalogue/warehouses", status_code=302)


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
        return RedirectResponse("/catalogue/warehouses", status_code=302)

    return templates.TemplateResponse("warehouses/form.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "error": None,
        "regions": _get_regions(db),
    })


from sqlalchemy.sql import func
from app.models.product_warehouse import ProductWarehouseStock
from app.models.product import Product


def _check_warehouse_stock(db: Session, wh_id: int) -> int:
    wh_stock = db.query(func.sum(ProductWarehouseStock.stock_qty)).filter(
        ProductWarehouseStock.warehouse_id == wh_id,
        ProductWarehouseStock.is_active == True
    ).scalar() or 0

    legacy_stock = db.query(func.sum(Product.stock_qty)).filter(
        Product.warehouse_id == wh_id,
        Product.is_active == True
    ).scalar() or 0

    return int(wh_stock + legacy_stock)


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
        return RedirectResponse("/catalogue/warehouses", status_code=302)

    if db.query(Warehouse).filter(Warehouse.code == code.upper(), Warehouse.id != wh_id).first():
        return templates.TemplateResponse("warehouses/form.html", {
            "request": request,
            "current_user": current_user,
            "item": item,
            "error": f"Warehouse code '{code.upper()}' already in use.",
            "regions": _get_regions(db),
        })

    # Validate inventory stock before deactivating warehouse
    new_is_active = is_active == "on"
    if item.is_active and not new_is_active:
        total_stock = _check_warehouse_stock(db, wh_id)
        if total_stock > 0:
            return templates.TemplateResponse("warehouses/form.html", {
                "request": request,
                "current_user": current_user,
                "item": item,
                "error": f"Cannot deactivate warehouse '{item.name}' because inventory stock ({total_stock} units) is present. Clear or adjust stock to 0 before deactivation.",
                "regions": _get_regions(db),
            })

    item.name = name
    item.code = code.upper()
    item.pincode = pincode or None
    item.address = address or None
    item.geography_id = int(geography_id) if geography_id else None
    item.is_active = new_is_active

    db.commit()
    set_flash_success(request, f"Warehouse '{name}' updated.")
    return RedirectResponse("/catalogue/warehouses", status_code=302)


@router.post("/{wh_id}/delete")
async def warehouse_deactivate(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if item:
        total_stock = _check_warehouse_stock(db, wh_id)
        if total_stock > 0:
            set_flash_error(request, f"Cannot deactivate warehouse '{item.name}' because inventory stock ({total_stock} units) is present. Clear or adjust stock to 0 before deactivation.")
            return RedirectResponse("/catalogue/warehouses", status_code=302)

        item.is_active = False
        db.commit()
        set_flash_success(request, f"Warehouse '{item.name}' deactivated successfully.")
    return RedirectResponse("/catalogue/warehouses", status_code=302)


@router.post("/{wh_id}/activate")
async def warehouse_activate(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if item:
        item.is_active = True
        db.commit()
        set_flash_success(request, f"Warehouse '{item.name}' activated successfully.")
    return RedirectResponse("/warehouses", status_code=302)
