import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.order import Order, OrderStatus, SyncStatus
from app.models.payment import Payment, PaymentStatus
from app.models.material_request import MaterialRequest, MRStatus, MRSyncStatus
from app.models.asset_capitalization import AssetCapitalization, ACStatus, ACSyncStatus
from app.models.local_distribution import LocalChannelPartner, PincodeTerritoryMapping

logger = logging.getLogger(__name__)


def confirm_order_natively(order: Order, db: Session) -> Order:
    """Confirm once and atomically deduct stock for company orders."""
    locked_order = (
        db.query(Order)
        .filter(Order.id == order.id)
        .with_for_update()
        .one()
    )
    if locked_order.status in {
        OrderStatus.confirmed,
        OrderStatus.dispatched,
        OrderStatus.delivered,
    }:
        return locked_order
    if locked_order.status not in {OrderStatus.draft, OrderStatus.submitted}:
        raise ValueError(
            f"Order in {locked_order.status.value} state cannot be confirmed."
        )

    if locked_order.is_company_order:
        if not locked_order.warehouse_id:
            raise ValueError("Company order has no warehouse for stock deduction.")
        from app.services.inventory_service import record_stock_movement

        for item in locked_order.items:
            record_stock_movement(
                db=db,
                product_id=item.product_id,
                warehouse_id=locked_order.warehouse_id,
                movement_type="OUTWARD",
                quantity=item.quantity,
                reference_no=locked_order.order_number,
                notes=f"Confirmed company order {locked_order.order_number}",
                created_by_id=locked_order.user_id,
                commit=False,
            )

    locked_order.status = OrderStatus.confirmed
    locked_order.sync_status = SyncStatus.synced
    locked_order.sync_error = None
    locked_order.sync_retries = 0
    db.commit()
    db.refresh(locked_order)
    logger.info(
        "Order %s natively confirmed locally", locked_order.order_number
    )

    # Trigger instant notification upon approval
    from app.services.channel_partner_notification import trigger_instant_order_notification
    trigger_instant_order_notification(db, locked_order)

    return locked_order


def record_payment_natively(payment: Payment, db: Session) -> Payment:
    """Natively records a payment collection with bill denomination breakdown."""
    payment.status = PaymentStatus.collected
    db.commit()
    db.refresh(payment)
    logger.info("Payment %s natively recorded locally", payment.payment_ref)
    return payment


def approve_material_request_natively(mr: MaterialRequest, db: Session) -> MaterialRequest:
    """Mark native synchronization successful without skipping workflow states."""
    mr.sync_status = MRSyncStatus.synced
    mr.sync_error = None
    mr.sync_retries = 0
    db.commit()
    db.refresh(mr)
    logger.info("Material request %s natively approved locally", mr.mr_number)
    return mr


def deploy_asset_capitalization_natively(ac: AssetCapitalization, db: Session) -> AssetCapitalization:
    """Natively deploys an asset capitalization."""
    ac.status = ACStatus.deployed
    ac.sync_status = ACSyncStatus.synced
    ac.sync_error = None
    ac.sync_retries = 0
    db.commit()
    db.refresh(ac)
    logger.info("Asset capitalization %s natively deployed locally", ac.ac_number)
    return ac


def resolve_territory_natively(pincode: str, db: Session) -> Dict[str, Any]:
    """Resolves territory information from local pincode mapping table."""
    mapping = db.query(PincodeTerritoryMapping).filter(
        PincodeTerritoryMapping.pincode == str(pincode),
        PincodeTerritoryMapping.is_active == True
    ).first()

    if mapping:
        return {
            "pincode": mapping.pincode,
            "territory": mapping.territory_name,
            "region": mapping.region_name or "Default Region",
            "state": mapping.state_name or "Default State"
        }

    return {
        "pincode": str(pincode),
        "territory": "General Territory",
        "region": "General Region",
        "state": "General State"
    }


def assign_channel_partner_natively(territory_name: str, service_category: Optional[str], db: Session) -> Optional[LocalChannelPartner]:
    """Assigns a local channel partner based on territory and service category."""
    query = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True)
    
    if territory_name:
        query = query.filter(LocalChannelPartner.territory_name == territory_name)
    if service_category:
        query = query.filter(LocalChannelPartner.service_category == service_category)

    partner = query.first()
    if not partner:
        # Fallback to any active partner
        partner = db.query(LocalChannelPartner).filter(LocalChannelPartner.is_active == True).first()

    return partner
