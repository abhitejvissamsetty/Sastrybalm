import logging
from sqlalchemy.orm import Session
from app.models.order import Order
from app.services.native_operations_service import confirm_order_natively

logger = logging.getLogger(__name__)


async def sync_order_to_connect(order: Order, db: Session) -> None:
    """Native local order confirmation replacement for CONNECT sync."""
    confirm_order_natively(order, db)


async def sync_order_to_zap(order: Order, db: Session) -> None:
    """Native local order confirmation replacement for ZAP sync."""
    confirm_order_natively(order, db)
