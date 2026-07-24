import csv
import io
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.product import Product, ProductCategory
from app.models.warehouse import Warehouse
from app.models.user import User, UserRole
from app.utils.csv_import import parse_csv_bytes
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

router = APIRouter(prefix="/products", tags=["products"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def product_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    q: str = Query(default=""),
    category_type: str = Query(default=""),
    must_sell: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    query = db.query(Product).filter(Product.is_active == True)
    if q:
        query = query.filter(Product.name.ilike(f"%{q}%") | Product.erp_id.ilike(f"%{q}%") | Product.sku.ilike(f"%{q}%"))
    if category_type and category_type in [c.value for c in ProductCategory]:
        query = query.filter(Product.category_type == category_type)
    if must_sell == "yes":
        query = query.filter(Product.must_sell == True)
    elif must_sell == "no":
        query = query.filter(Product.must_sell == False)
    query = query.order_by(Product.name)
    pagination = paginate(query, page)

    return templates.TemplateResponse("products/list.html", {
        "request": request, "current_user": current_user,
        "pagination": pagination, "q": q, "category_type": category_type, "must_sell": must_sell,
        "ProductCategory": ProductCategory,
        **get_flash(request),
    })


@router.get("/new", response_class=HTMLResponse)
async def product_new(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    return templates.TemplateResponse("products/form.html", {
        "request": request, "current_user": current_user, "item": None, "warehouses": warehouses, "ProductCategory": ProductCategory, "error": None,
    })


@router.post("/new")
async def product_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    erp_id: Optional[str] = Form(default=None),
    sku: Optional[str] = Form(default=None),
    division: Optional[str] = Form(default=None),
    category_type: str = Form(default=ProductCategory.sales.value),
    primary_category: Optional[str] = Form(default=None),
    secondary_category: Optional[str] = Form(default=None),
    mrp: Optional[str] = Form(default=None),
    unit_cost: Optional[str] = Form(default=None),
    stock_qty: int = Form(default=0),
    reorder_level: int = Form(default=10),
    warehouse_id: Optional[str] = Form(default=None),
    warehouse_location: Optional[str] = Form(default=None),
    gst_rate: Optional[str] = Form(default=None),
    must_sell: Optional[str] = Form(default=None),
):
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    try:
        mrp_val = Decimal(mrp) if mrp else Decimal("0")
        cost_val = Decimal(unit_cost) if unit_cost else Decimal("0")
        gst_val = Decimal(gst_rate) if gst_rate else Decimal("0")
    except Exception:
        return templates.TemplateResponse("products/form.html", {
            "request": request, "current_user": current_user, "item": None, "warehouses": warehouses, "ProductCategory": ProductCategory,
            "error": "MRP, Unit cost, and GST rate must be valid numbers.",
        })

    product = Product(
        name=name, erp_id=erp_id or None, sku=sku or None,
        division=division or None,
        category_type=ProductCategory(category_type) if category_type in [c.value for c in ProductCategory] else ProductCategory.sales,
        primary_category=primary_category or None,
        secondary_category=secondary_category or None,
        mrp=mrp_val, unit_cost=cost_val,
        stock_qty=stock_qty, reorder_level=reorder_level,
        warehouse_id=int(warehouse_id) if warehouse_id else None,
        warehouse_location=warehouse_location or None,
        gst_rate=gst_val, must_sell=must_sell == "on",
    )
    db.add(product)
    db.commit()
    set_flash_success(request, f"Product '{name}' created.")
    return RedirectResponse("/inventory", status_code=302)


@router.get("/{product_id}/edit", response_class=HTMLResponse)
async def product_edit(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if not item:
        set_flash_error(request, "Product not found.")
        return RedirectResponse("/products", status_code=302)
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    return templates.TemplateResponse("products/form.html", {
        "request": request, "current_user": current_user, "item": item, "warehouses": warehouses, "ProductCategory": ProductCategory, "error": None,
    })


@router.post("/{product_id}/edit")
async def product_update(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    erp_id: Optional[str] = Form(default=None),
    sku: Optional[str] = Form(default=None),
    division: Optional[str] = Form(default=None),
    category_type: str = Form(default=ProductCategory.sales.value),
    primary_category: Optional[str] = Form(default=None),
    secondary_category: Optional[str] = Form(default=None),
    mrp: Optional[str] = Form(default=None),
    unit_cost: Optional[str] = Form(default=None),
    stock_qty: int = Form(default=0),
    reorder_level: int = Form(default=10),
    warehouse_id: Optional[str] = Form(default=None),
    warehouse_location: Optional[str] = Form(default=None),
    gst_rate: Optional[str] = Form(default=None),
    must_sell: Optional[str] = Form(default=None),
    is_active: Optional[str] = Form(default=None),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if not item:
        set_flash_error(request, "Product not found.")
        return RedirectResponse("/products", status_code=302)

    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    try:
        item.mrp = Decimal(mrp) if mrp else Decimal("0")
        item.unit_cost = Decimal(unit_cost) if unit_cost else Decimal("0")
        item.gst_rate = Decimal(gst_rate) if gst_rate else Decimal("0")
    except Exception:
        return templates.TemplateResponse("products/form.html", {
            "request": request, "current_user": current_user, "item": item, "warehouses": warehouses, "ProductCategory": ProductCategory,
            "error": "MRP, Unit cost, and GST rate must be valid numbers.",
        })

    item.name = name
    item.erp_id = erp_id or None
    item.sku = sku or None
    item.division = division or None
    if category_type in [c.value for c in ProductCategory]:
        item.category_type = ProductCategory(category_type)
    item.primary_category = primary_category or None
    item.secondary_category = secondary_category or None
    item.stock_qty = stock_qty
    item.reorder_level = reorder_level
    item.warehouse_id = int(warehouse_id) if warehouse_id else None
    item.warehouse_location = warehouse_location or None
    item.must_sell = must_sell == "on"
    item.is_active = is_active == "on"

    db.commit()
    set_flash_success(request, f"Product '{name}' updated.")
    return RedirectResponse("/inventory", status_code=302)


@router.post("/{product_id}/delete")
async def product_delete(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if item:
        item.is_active = False
        db.commit()
        set_flash_success(request, f"'{item.name}' deactivated.")
    return RedirectResponse("/inventory", status_code=302)
