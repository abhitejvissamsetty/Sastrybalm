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


@router.get("", response_class=HTMLResponse)
async def inventory_list(
    request: Request,
    current_user: User = Depends(require_web_auth),
    db: Session = Depends(get_db),
    query_str: str = Query(default=""),
    page: int = Query(default=1, ge=1),
):
    """View products catalogue and current stock inventory balances."""
    query = db.query(Product).filter(Product.is_active == True)
    if query_str:
        query = query.filter(
            Product.name.ilike(f"%{query_str}%") | 
            Product.sku.ilike(f"%{query_str}%") |
            Product.primary_category.ilike(f"%{query_str}%")
        )
    query = query.order_by(Product.name.asc())
    pagination = paginate(query, page)

    return templates.TemplateResponse("inventory/list.html", {
        "request": request,
        "current_user": current_user,
        "pagination": pagination,
        "query_str": query_str,
        **get_flash(request),
    })


@router.post("/stock-inward")
async def inventory_stock_inward(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin, UserRole.territory_manager)),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    quantity: int = Form(...),
    reference_no: Optional[str] = Form(default=None),
    notes: Optional[str] = Form(default=None),
):
    """Add incoming stock to inventory."""
    try:
        record_stock_movement(
            db=db,
            product_id=product_id,
            movement_type="INWARD",
            quantity=quantity,
            reference_no=reference_no,
            notes=notes,
            created_by_id=current_user.id
        )
        set_flash_success(request, f"Added {quantity} units to stock inward.")
    except Exception as exc:
        set_flash_error(request, f"Failed to record stock inward: {exc}")

    return RedirectResponse("/inventory", status_code=302)


@router.post("/adjust")
async def inventory_stock_adjust(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    product_id: int = Form(...),
    new_quantity: int = Form(...),
    notes: Optional[str] = Form(default=None),
):
    """Adjust stock quantity manually."""
    try:
        record_stock_movement(
            db=db,
            product_id=product_id,
            movement_type="ADJUSTMENT",
            quantity=new_quantity,
            notes=notes,
            created_by_id=current_user.id
        )
        set_flash_success(request, f"Product stock adjusted to {new_quantity}.")
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
    query = db.query(StockMovement).order_by(StockMovement.created_at.desc())
    pagination = paginate(query, page)

    return templates.TemplateResponse("inventory/movements.html", {
        "request": request,
        "current_user": current_user,
        "pagination": pagination,
        **get_flash(request),
    })
