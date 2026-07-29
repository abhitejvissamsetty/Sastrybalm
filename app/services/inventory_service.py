import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.product_warehouse import ProductWarehouseStock
from app.models.inventory import StockMovement

logger = logging.getLogger(__name__)


def record_stock_movement(
    db: Session,
    product_id: int,
    movement_type: str,  # INWARD, OUTWARD, ADJUSTMENT
    quantity: int,
    warehouse_id: Optional[int] = None,
    reference_no: Optional[str] = None,
    notes: Optional[str] = None,
    created_by_id: Optional[int] = None,
    *,
    commit: bool = True,
) -> StockMovement:
    """Logs stock movement and updates current product & warehouse stock balances."""
    if movement_type not in {"INWARD", "OUTWARD", "ADJUSTMENT"}:
        raise ValueError(f"Unsupported stock movement type: {movement_type}.")
    if quantity < 0:
        raise ValueError("Stock quantity cannot be negative.")

    product = (
        db.query(Product)
        .filter(Product.id == product_id)
        .with_for_update()
        .first()
    )
    if not product:
        raise ValueError(f"Product ID {product_id} not found.")

    pws = None
    if warehouse_id:
        pws = db.query(ProductWarehouseStock).filter(
            ProductWarehouseStock.product_id == product_id,
            ProductWarehouseStock.warehouse_id == warehouse_id
        ).with_for_update().first()
        if not pws:
            pws = ProductWarehouseStock(
                product_id=product_id,
                warehouse_id=warehouse_id,
                stock_qty=0
            )
            db.add(pws)
            db.flush()

        if movement_type == "INWARD":
            pws.stock_qty += quantity
        elif movement_type == "OUTWARD":
            if pws.stock_qty < quantity:
                raise ValueError(
                    f"Insufficient stock: requested {quantity}, available {pws.stock_qty}."
                )
            pws.stock_qty -= quantity
        elif movement_type == "ADJUSTMENT":
            pws.stock_qty = quantity
    else:
        if movement_type == "INWARD":
            product.stock_qty += quantity
        elif movement_type == "OUTWARD":
            if product.stock_qty < quantity:
                raise ValueError(
                    f"Insufficient stock: requested {quantity}, available {product.stock_qty}."
                )
            product.stock_qty -= quantity
        elif movement_type == "ADJUSTMENT":
            product.stock_qty = quantity

    # Recalculate total product stock_qty across all assigned warehouses
    all_stocks = db.query(ProductWarehouseStock).filter(
        ProductWarehouseStock.product_id == product_id,
        ProductWarehouseStock.is_active == True
    ).all()
    if all_stocks:
        product.stock_qty = sum(s.stock_qty for s in all_stocks)
    elif warehouse_id and pws:
        product.stock_qty = pws.stock_qty

    movement = StockMovement(
        product_id=product_id,
        warehouse_id=warehouse_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_no=reference_no,
        notes=notes,
        created_by_id=created_by_id
    )
    db.add(movement)
    if commit:
        db.commit()
        db.refresh(movement)
    else:
        db.flush()
    logger.info("Stock movement recorded: %s %d units for product %s in WH %s (Total Stock: %d)", movement_type, quantity, product.name, str(warehouse_id), product.stock_qty)
    return movement
