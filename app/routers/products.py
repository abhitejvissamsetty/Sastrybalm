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
from app.models.product_warehouse import ProductWarehouseStock
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
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    return templates.TemplateResponse("products/form.html", {
        "request": request, "current_user": current_user, "item": None, "warehouses": warehouses, "ProductCategory": ProductCategory, "error": None,
    })


@router.post("/new")
async def product_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
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
    is_stockable: Optional[str] = Form(default=None),
):
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    try:
        mrp_val = Decimal(mrp) if mrp else Decimal("0")
        cost_val = Decimal(unit_cost) if unit_cost else Decimal("0")
        gst_val = Decimal(gst_rate) if gst_rate else Decimal("0")
    except Exception:
        return templates.TemplateResponse("products/form.html", {
            "request": request, "current_user": current_user, "item": None, "warehouses": warehouses, "ProductCategory": ProductCategory,
            "error": "MRP, Price to Retailer (PTR), and GST rate must be valid numbers.",
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
        gst_rate=gst_val,
        must_sell=must_sell == "on",
        is_stockable=is_stockable == "on",
    )
    db.add(product)
    db.commit()
    set_flash_success(request, f"Product '{name}' created.")
    return RedirectResponse("/products", status_code=302)


@router.get("/{product_id}/edit", response_class=HTMLResponse)
async def product_edit(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
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
    current_user: User = Depends(require_web_roles(UserRole.admin)),
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
    is_stockable: Optional[str] = Form(default=None),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if not item:
        set_flash_error(request, "Product not found.")
        return RedirectResponse("/products", status_code=302)

    try:
        mrp_val = Decimal(mrp) if mrp else Decimal("0")
        cost_val = Decimal(unit_cost) if unit_cost else Decimal("0")
        gst_val = Decimal(gst_rate) if gst_rate else Decimal("0")
    except Exception:
        warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
        return templates.TemplateResponse("products/form.html", {
            "request": request, "current_user": current_user, "item": item, "warehouses": warehouses, "ProductCategory": ProductCategory,
            "error": "MRP, Price to Retailer (PTR), and GST rate must be valid numbers.",
        })

    item.name = name
    item.erp_id = erp_id or None
    item.sku = sku or None
    item.division = division or None
    item.category_type = ProductCategory(category_type) if category_type in [c.value for c in ProductCategory] else ProductCategory.sales
    item.primary_category = primary_category or None
    item.secondary_category = secondary_category or None
    item.mrp = mrp_val
    item.unit_cost = cost_val
    item.stock_qty = stock_qty
    item.reorder_level = reorder_level
    item.warehouse_id = int(warehouse_id) if warehouse_id else None
    item.warehouse_location = warehouse_location or None
    item.gst_rate = gst_val
    item.must_sell = must_sell == "on"
    item.is_stockable = is_stockable == "on"

    db.commit()
    set_flash_success(request, f"Product '{name}' updated.")
    return RedirectResponse("/products", status_code=302)


@router.post("/{product_id}/delete")
async def product_delete(
    product_id: int, request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if item:
        # Check stock quantity in product model
        total_stock = item.stock_qty or 0
        
        # Check total stock quantity across all attached warehouses
        wh_stocks = db.query(ProductWarehouseStock).filter(
            ProductWarehouseStock.product_id == product_id,
            ProductWarehouseStock.is_active == True
        ).all()
        if wh_stocks:
            total_stock += sum(s.stock_qty for s in wh_stocks)
            
        if total_stock > 0:
            set_flash_error(request, f"Cannot deactivate product '{item.name}' because stock ({total_stock} units) is present. Clear or adjust stock to 0 before deactivation.")
            return RedirectResponse("/products", status_code=302)

        item.is_active = False
        db.commit()
        set_flash_success(request, f"Product '{item.name}' deactivated successfully.")
    return RedirectResponse("/products", status_code=302)


@router.get("/{product_id}/attach-warehouses", response_class=HTMLResponse)
async def product_attach_warehouses_get(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active product not found.")
        return RedirectResponse("/inventory", status_code=302)

    all_warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()
    assigned_stocks = db.query(ProductWarehouseStock).filter(
        ProductWarehouseStock.product_id == product_id,
        ProductWarehouseStock.is_active == True
    ).all()
    assigned_warehouse_ids = [s.warehouse_id for s in assigned_stocks]

    # Include legacy warehouse assignment if not in product_warehouse_stocks
    if item.warehouse_id and item.warehouse_id not in assigned_warehouse_ids:
        assigned_warehouse_ids.append(item.warehouse_id)

    return templates.TemplateResponse("products/attach_warehouses.html", {
        "request": request,
        "current_user": current_user,
        "item": item,
        "all_warehouses": all_warehouses,
        "assigned_warehouse_ids": assigned_warehouse_ids,
        **get_flash(request),
    })


@router.post("/{product_id}/attach-warehouses")
async def product_attach_warehouses_post(
    product_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    warehouse_ids: list[str] = Form(default=[]),
):
    item = db.query(Product).filter(Product.id == product_id).first()
    if not item or not item.is_active:
        set_flash_error(request, "Active product not found.")
        return RedirectResponse("/inventory", status_code=302)

    form_data = await request.form()
    raw_wh_ids = form_data.getlist("warehouse_ids")
    target_ids = [int(w) for w in (raw_wh_ids or warehouse_ids) if w and str(w).isdigit()]

    existing_stocks = db.query(ProductWarehouseStock).filter(
        ProductWarehouseStock.product_id == product_id
    ).all()

    existing_dict = {s.warehouse_id: s for s in existing_stocks}

    # 1. Attach/Activate new warehouses
    for wh_id in target_ids:
        if wh_id in existing_dict:
            existing_dict[wh_id].is_active = True
        else:
            new_pws = ProductWarehouseStock(
                product_id=product_id,
                warehouse_id=wh_id,
                stock_qty=0,
                is_active=True
            )
            db.add(new_pws)

    # 2. Deactivate/Remove warehouses not in target_ids
    for wh_id, pws in existing_dict.items():
        if wh_id not in target_ids and pws.is_active:
            if pws.stock_qty > 0:
                wh_obj = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
                wh_name = wh_obj.name if wh_obj else f"ID {wh_id}"
                set_flash_error(
                    request,
                    f"Cannot remove warehouse '{wh_name}'. Stock is present ({pws.stock_qty} units). Please clear inventory stock first."
                )
                return RedirectResponse(f"/products/{product_id}/attach-warehouses", status_code=302)
            db.delete(pws)

    db.commit()

    # Recalculate total product stock
    all_stocks = db.query(ProductWarehouseStock).filter(
        ProductWarehouseStock.product_id == product_id,
        ProductWarehouseStock.is_active == True
    ).all()
    item.stock_qty = sum(s.stock_qty for s in all_stocks)
    db.commit()

    set_flash_success(request, f"Warehouse attachments updated for product '{item.name}'.")
    return RedirectResponse("/inventory", status_code=302)
