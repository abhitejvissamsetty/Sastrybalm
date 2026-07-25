import logging
from typing import Optional

from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.product import Product
from app.models.inventory import StockMovement
from app.models.user import User, UserRole
from app.services.inventory_service import record_stock_movement
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="app/templates")


from app.models.warehouse import Warehouse


from fastapi import APIRouter, Depends, Form, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session, joinedload

from app.dependencies import get_db, require_web_auth, require_web_roles
from app.models.product import Product
from app.models.product_warehouse import ProductWarehouseStock
from app.models.inventory import StockMovement
from app.models.warehouse import Warehouse
from app.models.user import User, UserRole
from app.services.inventory_service import record_stock_movement
from app.utils.flash import get_flash, set_flash_error, set_flash_success
from app.utils.pagination import paginate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/inventory", tags=["inventory"])
templates = Jinja2Templates(directory="app/templates")


@router.get("", response_class=HTMLResponse)
async def inventory_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    query_str: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    """View inventory balances and warehouse assignments for stockable products."""
    query = (
        db.query(Product)
        .options(joinedload(Product.warehouse_stocks).joinedload(ProductWarehouseStock.warehouse))
        .filter(Product.is_active == True, Product.is_stockable == True)
    )
    if query_str:
        query = query.filter(
            Product.name.ilike(f"%{query_str}%") | 
            Product.sku.ilike(f"%{query_str}%") |
            Product.primary_category.ilike(f"%{query_str}%")
        )
    query = query.order_by(Product.name.asc())
    pagination = paginate(query, page)
    warehouses = db.query(Warehouse).filter(Warehouse.is_active == True).order_by(Warehouse.name).all()

    return templates.TemplateResponse("inventory/list.html", {
        "request": request,
        "current_user": current_user,
        "pagination": pagination,
        "query_str": query_str,
        "warehouses": warehouses,
        **get_flash(request),
    })


@router.get("/product/{product_id}/warehouse-details")
async def inventory_product_warehouse_details(
    product_id: int,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
):
    """JSON details endpoint for a product's multi-warehouse stock breakdown."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        return JSONResponse({"error": "Product not found"}, status_code=404)

    stocks = (
        db.query(ProductWarehouseStock)
        .options(joinedload(ProductWarehouseStock.warehouse))
        .filter(ProductWarehouseStock.product_id == product_id, ProductWarehouseStock.is_active == True)
        .all()
    )

    items = []
    total_qty = 0
    for s in stocks:
        total_qty += s.stock_qty
        items.append({
            "id": s.id,
            "warehouse_id": s.warehouse_id,
            "warehouse_name": s.warehouse.name if s.warehouse else "Unknown",
            "warehouse_code": s.warehouse.code if s.warehouse else "N/A",
            "warehouse_location": s.warehouse_location or "—",
            "stock_qty": s.stock_qty,
            "reorder_level": s.reorder_level,
            "status": "Low Stock" if s.stock_qty <= s.reorder_level else "Optimal Stock",
        })

    # If product has legacy warehouse_id but no entry in product_warehouse_stocks
    if not items and product.warehouse:
        items.append({
            "id": 0,
            "warehouse_id": product.warehouse_id,
            "warehouse_name": product.warehouse.name,
            "warehouse_code": product.warehouse.code,
            "warehouse_location": product.warehouse_location or "—",
            "stock_qty": product.stock_qty,
            "reorder_level": product.reorder_level,
            "status": "Low Stock" if product.stock_qty <= product.reorder_level else "Optimal Stock",
        })
        total_qty = product.stock_qty

    return JSONResponse({
        "product_id": product.id,
        "product_name": product.name,
        "sku": product.sku or product.erp_id or "—",
        "total_stock": product.stock_qty,
        "warehouses": items
    })


@router.post("/assign-warehouse")
async def inventory_assign_warehouse(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    warehouse_id: int = Form(...),
    warehouse_location: Optional[str] = Form(default=None),
    reorder_level: Optional[int] = Form(default=10),
):
    """Assign or update warehouse and location for a stockable product."""
    product = db.query(Product).filter(Product.id == product_id, Product.is_stockable == True).first()
    if not product:
        set_flash_error(request, "Stockable product not found.")
        return RedirectResponse("/inventory", status_code=302)

    wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id, Warehouse.is_active == True).first()
    if not wh:
        set_flash_error(request, "Selected warehouse not found or inactive.")
        return RedirectResponse("/inventory", status_code=302)

    pws = db.query(ProductWarehouseStock).filter(
        ProductWarehouseStock.product_id == product_id,
        ProductWarehouseStock.warehouse_id == warehouse_id
    ).first()

    if not pws:
        pws = ProductWarehouseStock(
            product_id=product_id,
            warehouse_id=warehouse_id,
            stock_qty=0,
            reorder_level=reorder_level or 10,
            warehouse_location=warehouse_location or None
        )
        db.add(pws)
    else:
        pws.warehouse_location = warehouse_location or None
        if reorder_level is not None:
            pws.reorder_level = reorder_level
        pws.is_active = True

    # Maintain primary warehouse fields on Product for backward compatibility
    product.warehouse_id = warehouse_id
    if warehouse_location:
        product.warehouse_location = warehouse_location

    db.commit()
    set_flash_success(request, f"Attached warehouse '{wh.name}' to product '{product.name}'.")
    return RedirectResponse("/inventory", status_code=302)


@router.post("/remove-warehouse")
async def inventory_remove_warehouse(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    warehouse_id: int = Form(...),
):
    """Remove warehouse assignment from product."""
    pws = db.query(ProductWarehouseStock).filter(
        ProductWarehouseStock.product_id == product_id,
        ProductWarehouseStock.warehouse_id == warehouse_id
    ).first()

    if pws:
        if pws.stock_qty > 0:
            set_flash_error(request, f"Cannot remove warehouse. Stock is present ({pws.stock_qty} units). Clear stock first.")
            return RedirectResponse("/inventory", status_code=302)
        
        db.delete(pws)
        db.commit()

        # Recalculate total product stock
        product = db.query(Product).filter(Product.id == product_id).first()
        if product:
            all_stocks = db.query(ProductWarehouseStock).filter(
                ProductWarehouseStock.product_id == product_id,
                ProductWarehouseStock.is_active == True
            ).all()
            product.stock_qty = sum(s.stock_qty for s in all_stocks)
            db.commit()

        set_flash_success(request, "Warehouse unassigned from product successfully.")
    return RedirectResponse("/inventory", status_code=302)


@router.post("/stock-inward")
async def inventory_stock_inward(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    warehouse_id: Optional[str] = Form(default=None),
    quantity: int = Form(...),
    reference_no: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
):
    """Add incoming stock to a specific warehouse."""
    if not warehouse_id:
        set_flash_error(request, "Please select a warehouse for stock inward.")
        return RedirectResponse("/inventory", status_code=302)

    try:
        wh_id = int(warehouse_id)
        wh = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
        record_stock_movement(
            db=db,
            product_id=product_id,
            warehouse_id=wh_id,
            movement_type="INWARD",
            quantity=quantity,
            reference_no=reference_no,
            notes=notes,
            created_by_id=current_user.id
        )
        set_flash_success(request, f"Added {quantity} units to '{wh.name if wh else 'Warehouse'}'.")
    except Exception as exc:
        set_flash_error(request, f"Failed to record stock inward: {exc}")

    return RedirectResponse("/inventory", status_code=302)


@router.post("/adjust")
async def inventory_stock_adjust(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    warehouse_id: Optional[str] = Form(default=None),
    new_quantity: int = Form(...),
    notes: Optional[str] = Form(default=None),
):
    """Adjust stock quantity for a specific warehouse."""
    if not warehouse_id:
        set_flash_error(request, "Please select a warehouse for stock adjustment.")
        return RedirectResponse("/inventory", status_code=302)

    try:
        wh_id = int(warehouse_id)
        wh = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
        record_stock_movement(
            db=db,
            product_id=product_id,
            warehouse_id=wh_id,
            movement_type="ADJUSTMENT",
            quantity=new_quantity,
            notes=notes,
            created_by_id=current_user.id
        )
        set_flash_success(request, f"Adjusted stock in '{wh.name if wh else 'Warehouse'}' to {new_quantity} units.")
    except Exception as exc:
        set_flash_error(request, f"Failed to adjust stock: {exc}")

    return RedirectResponse("/inventory", status_code=302)


@router.get("/movements", response_class=HTMLResponse)
async def inventory_movements(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    page: int = Query(default=1, ge=1),
):
    """Audit trail log of all stock movements."""
    query = (
        db.query(StockMovement)
        .options(
            joinedload(StockMovement.product),
            joinedload(StockMovement.warehouse)
        )
        .order_by(StockMovement.created_at.desc())
    )
    pagination = paginate(query, page)

    return templates.TemplateResponse("inventory/movements.html", {
        "request": request,
        "current_user": current_user,
        "pagination": pagination,
        **get_flash(request),
    })
