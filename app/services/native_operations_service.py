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
    """Natively confirms an order without third-party API dependencies."""
    order.status = OrderStatus.confirmed
    order.sync_status = SyncStatus.synced
    order.sync_error = None
    order.sync_retries = 0
    if not order.connect_ref:
        order.connect_ref = f"ORD-NATIVE-{order.id}"
    db.commit()
    db.refresh(order)
    logger.info("Order %s natively confirmed locally", order.order_number)
    return order


def record_payment_natively(payment: Payment, db: Session) -> Payment:
    """Natively records a payment collection with bill denomination breakdown."""
    payment.status = PaymentStatus.collected
    db.commit()
    db.refresh(payment)
    logger.info("Payment %s natively recorded locally", payment.payment_ref)
    return payment


def approve_material_request_natively(mr: MaterialRequest, db: Session) -> MaterialRequest:
    """Natively approves a material request."""
    mr.status = MRStatus.approved
    mr.sync_status = MRSyncStatus.synced
    mr.sync_error = None
    mr.sync_retries = 0
    if not mr.cmms_ref:
        mr.cmms_ref = f"MR-NATIVE-{mr.id}"
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
    if not ac.cmms_ref:
        ac.cmms_ref = f"AC-NATIVE-{ac.id}"
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
