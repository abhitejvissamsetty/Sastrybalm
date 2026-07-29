import logging
from sqlalchemy.orm import Session
from app.models.order import Order
from app.services.native_operations_service import confirm_order_natively

logger = logging.getLogger(__name__)


async def sync_order_to_zap(order: Order, db: Session) -> None:
    """Confirm an order through the native local workflow."""
    confirm_order_natively(order, db)
