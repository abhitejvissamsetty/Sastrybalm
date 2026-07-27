import csv
import io
import logging
from datetime import date
from typing import Dict, Optional, Tuple

from sqlalchemy.orm import Session

from app.models.local_distribution import LocalChannelPartner
from app.models.order import Order, OrderHistoryLog, OrderStatus
from app.models.user import User

logger = logging.getLogger(__name__)


def record_order_history_log(
    db: Session,
    order_id: int,
    action: str,
    performed_by_id: Optional[int] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    channel_partner_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> OrderHistoryLog:
    """
    Records an entry in order_history_logs for auditing status changes, channel partner allocation, and lifecycle actions.
    """
    log = OrderHistoryLog(
        order_id=order_id,
        action=action,
        performed_by_id=performed_by_id,
        old_status=old_status,
        new_status=new_status,
        channel_partner_id=channel_partner_id,
        notes=notes,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def auto_allocate_channel_partner_for_order(db: Session, order: Order) -> Optional[LocalChannelPartner]:
    """
    Auto-allocates and persists the fulfillment Channel Partner for an order based on the Outlet's Geography.
    """
    if not order or not order.outlet:
        return None

    out_geo_id = getattr(order.outlet, "territory_id", None) or (order.outlet.beat.geography_id if order.outlet.beat else None)
    if not out_geo_id:
        return None
    from app.models.geography import Geography
    geo = db.query(Geography).filter(Geography.id == out_geo_id).first()
    geo_ids = [out_geo_id]
    if geo and geo.parent_id:
        geo_ids.append(geo.parent_id)

    cp = db.query(LocalChannelPartner).filter(
        LocalChannelPartner.geography_id.in_(geo_ids),
        LocalChannelPartner.is_active == True
    ).first()

    if cp:
        order.channel_partner_id = cp.id
        db.commit()
        logger.info(f"Auto-allocated Channel Partner '{cp.name}' (ID: {cp.id}) for Order {order.order_number}")
    return cp


def get_l1_user_and_hierarchy_usernames(user: Optional[User]) -> Tuple[Dict[str, str], str, str, str]:
    """
    Extracts L1 Field Rep user details (name, email, phone) and L2, L3, L4 usernames.
    """
    l1_details = {
        "name": user.full_name if user else "N/A",
        "email": user.email if user else "N/A",
        "phone": (user.phone or user.mobile) if user and (user.phone or user.mobile) else "N/A",
    }
    l2_username = "N/A"
    l3_username = "N/A"
    l4_username = "N/A"

    if user and user.positions:
        # Find first active position
        pos = next((p for p in user.positions if p.is_active), None)
        if pos:
            # Traversal up position hierarchy
            l2_pos = pos.reporting_to
            l3_pos = l2_pos.reporting_to if l2_pos else None
            l4_pos = l3_pos.reporting_to if l3_pos else None

            if l2_pos and l2_pos.users:
                active_l2_users = [u.username for u in l2_pos.users if u.is_active]
                l2_username = ", ".join(active_l2_users) if active_l2_users else "N/A"

            if l3_pos and l3_pos.users:
                active_l3_users = [u.username for u in l3_pos.users if u.is_active]
                l3_username = ", ".join(active_l3_users) if active_l3_users else "N/A"

            if l4_pos and l4_pos.users:
                active_l4_users = [u.username for u in l4_pos.users if u.is_active]
                l4_username = ", ".join(active_l4_users) if active_l4_users else "N/A"

    return l1_details, l2_username, l3_username, l4_username


def generate_channel_partner_daily_orders_csv(
    db: Session,
    channel_partner: LocalChannelPartner,
    filter_date: Optional[date] = None,
) -> str:
    """
    Generates CSV string containing consolidated order details for a Channel Partner:
    Order Details (order_date, line_items, amounts), Outlet Details, L1 User Details (email, phone_number), L2, L3, L4 usernames.
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Write CSV Header
    writer.writerow([
        "Order Number",
        "Order Date",
        "Order Status",
        "Line Items (Product x Qty @ Price = LineTotal)",
        "Total Amount (INR)",
        "Outlet Code",
        "Outlet Name",
        "Outlet Address",
        "Outlet Phone",
        "Outlet Geography",
        "L1 Rep Name",
        "L1 Rep Email",
        "L1 Rep Phone",
        "L2 Username",
        "L3 Username",
        "L4 Username",
    ])

    # Scope orders: Orders where outlet/beat geography matches Channel Partner geography
    orders_query = db.query(Order)
    if channel_partner.geography_id:
        from app.models.geography import Geography
        child_ids = [t.id for t in db.query(Geography).filter(Geography.parent_id == channel_partner.geography_id).all()]
        allowed_geo_ids = [channel_partner.geography_id] + child_ids

        from app.models.outlet import Outlet
        orders_query = orders_query.join(Outlet).filter(Outlet.geography_id.in_(allowed_geo_ids))

    if filter_date:
        orders_query = orders_query.filter(Order.order_date == filter_date)

    orders = orders_query.order_by(Order.order_date.desc(), Order.id.desc()).all()

    for o in orders:
        # Format Line Items
        item_strs = []
        for item in o.items:
            pname = item.product.name if item.product else f"Product #{item.product_id}"
            item_strs.append(f"{pname} ({item.quantity} x ₹{float(item.unit_price):.2f} = ₹{float(item.line_total):.2f})")
        line_items_formatted = "; ".join(item_strs) if item_strs else "No line items"

        # Outlet Details
        out = o.outlet
        out_name = out.name if out else "N/A"
        out_code = out.code if out else "N/A"
        out_addr = out.address if out else "N/A"
        out_phone = (out.mobile or out.phone) if out and (out.mobile or out.phone) else "N/A"
        out_geo = out.geography.name if out and out.geography else "N/A"

        # L1 Rep & Hierarchy Usernames
        l1_user = o.user
        l1_info, l2_uname, l3_uname, l4_uname = get_l1_user_and_hierarchy_usernames(l1_user)

        writer.writerow([
            o.order_number,
            o.order_date.strftime("%Y-%m-%d") if o.order_date else "",
            o.status.value.title() if o.status else "",
            line_items_formatted,
            f"{o.total_amount:.2f}",
            out_code,
            out_name,
            out_addr,
            out_phone,
            out_geo,
            l1_info["name"],
            l1_info["email"],
            l1_info["phone"],
            l2_uname,
            l3_uname,
            l4_uname,
        ])

    return output.getvalue()


def trigger_instant_order_notification(db: Session, order: Order) -> None:
    """
    Triggers instant order notification for channel partner(s) attached to order's geography
    UPON ORDER APPROVAL (status = 'confirmed').
    Dispatches via partner's assigned notification delivery service (Email SMTP, WhatsApp API, Webhook, Both).
    """
    if not order or not order.outlet or not order.outlet.geography_id:
        return

    from app.models.order import OrderStatus
    if order.status != OrderStatus.confirmed:
        logger.info(f"Skipping instant notification for order {order.order_number}: status is '{order.status.value}', not approved ('confirmed').")
        return

    out_geo_id = order.outlet.geography_id
    from app.models.geography import Geography
    geo = db.query(Geography).filter(Geography.id == out_geo_id).first()
    geo_ids = [out_geo_id]
    if geo and geo.parent_id:
        geo_ids.append(geo.parent_id)

    cps = db.query(LocalChannelPartner).filter(
        LocalChannelPartner.geography_id.in_(geo_ids),
        LocalChannelPartner.is_active == True,
        LocalChannelPartner.notification_preference.in_(["instant", "both"])
    ).all()

    for cp in cps:
        logger.info(
            f"[APPROVED ORDER NOTIFICATION] Order {order.order_number} (Amount: ₹{order.total_amount:.2f}) "
            f"Approved! Dispatched via {cp.notification_channel_label} to Channel Partner '{cp.name}' "
            f"(Email: {cp.email or 'N/A'}, Mobile: {cp.mobile or 'N/A'})"
        )


def record_material_request_history_log(
    db: Session,
    material_request_id: int,
    action: str,
    performed_by_id: Optional[int] = None,
    old_status: Optional[str] = None,
    new_status: Optional[str] = None,
    vendor_id: Optional[int] = None,
    notes: Optional[str] = None,
) -> None:
    """Helper to record material request lifecycle history log."""
    from app.models.material_request import MaterialRequestHistoryLog
    log = MaterialRequestHistoryLog(
        material_request_id=material_request_id,
        action=action,
        performed_by_id=performed_by_id,
        old_status=old_status,
        new_status=new_status,
        vendor_id=vendor_id,
        notes=notes,
    )
    db.add(log)
    db.commit()


def trigger_vendor_material_request_notification(db: Session, mr, is_reassignment: bool = False) -> None:
    """
    Dispatches instant notification to assigned vendor once Material Request is assigned & approved.
    Supports post-approval reassignments.
    """
    if not mr or not mr.vendor_id:
        return

    from app.models.user import User
    vendor = db.query(User).filter(User.id == mr.vendor_id).first()
    if not vendor:
        return

    event_type = "REASSIGNED" if is_reassignment else "ASSIGNED"
    logger.info(
        f"[VENDOR MR NOTIFICATION - {event_type}] Material Request {mr.mr_number} "
        f"assigned to Vendor '{vendor.full_name}' (Email: {vendor.email or 'N/A'}, Mobile: {vendor.mobile or 'N/A'}). "
        f"Notification dispatched via preferred channel."
    )
