import logging
from typing import Optional, List
from sqlalchemy.orm import Session

from app.models.product import Product
from app.models.inventory import StockMovement

logger = logging.getLogger(__name__)


def record_stock_movement(
    db: Session,
    product_id: int,
    movement_type: str,  # INWARD, OUTWARD, ADJUSTMENT
    quantity: int,
    reference_no: Optional[str] = None,
    notes: Optional[str] = None,
    created_by_id: Optional[int] = None
) -> StockMovement:
    """Logs stock movement and updates current product stock balance."""
    product = db.query(Product).filter(Product.id == product_id).first()
    if not product:
        raise ValueError(f"Product ID {product_id} not found.")

    if movement_type == "INWARD":
        product.stock_qty += quantity
    elif movement_type == "OUTWARD":
        product.stock_qty = max(0, product.stock_qty - quantity)
    elif movement_type == "ADJUSTMENT":
        product.stock_qty = quantity  # Set exact stock quantity

    movement = StockMovement(
        product_id=product_id,
        movement_type=movement_type,
        quantity=quantity,
        reference_no=reference_no,
        notes=notes,
        created_by_id=created_by_id
    )
    db.add(movement)
    db.commit()
    db.refresh(movement)
    logger.info("Stock movement recorded: %s %d units for product %s (New Stock: %d)", movement_type, quantity, product.name, product.stock_qty)
    return movement
