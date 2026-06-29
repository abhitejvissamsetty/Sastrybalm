import logging
import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.adapters.connect import ConnectAdapter
from app.adapters.zap import ZapAdapter
from app.models.company import CompanyProfile
from app.models.order import Order, FlowType, SyncStatus
from app.models.product_mapping import ProductAliasMap
from app.models.alert import Alert, AlertSeverity, AlertType
from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)

async def sync_order_to_connect(order: Order, db: Session) -> None:
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == order.company_profile_id).first()
    if not profile or not profile.connect_base_url:
        order.sync_status = SyncStatus.failed
        order.sync_error = "CONNECT configuration missing for this company profile."
        db.commit()
        return

    api_key_secret = decrypt(profile.connect_api_key_encrypted)

    items_payload = []
    for it in order.items:
        alias = db.query(ProductAliasMap).filter(
            ProductAliasMap.company_profile_id == order.company_profile_id,
            ProductAliasMap.product_id == it.product_id
        ).first()

        connect_code = alias.connect_item_code if alias else (it.product.sku or it.product.erp_id)
        items_payload.append({
            "item": connect_code,
            "quantity": it.quantity,
            "item_rate": float(it.unit_price),
            "line_item_amount": float(it.line_total)
        })

    payload = {
        "order_date": order.created_at.strftime("%Y-%m-%d %H:%M:%S") if order.created_at else datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "ordered_by": order.user.email,
        "agent_code": order.user.employee_id or order.user.username,
        "delivery_address": order.outlet.name,
        "contact": order.outlet.owner_name or "N/A",
        "service_category": order.outlet.channel.value if (order.outlet and order.outlet.channel) else "General",
        "channel_partner": "",
        "order_notes": order.notes or "",
        "items": items_payload,
        "timeline": [
            {
                "event_type": "Status Update",
                "recorded_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "fieldname": "order_status",
                "from_value": "Submitted",
                "to_value": "Assigned",
                "created_by": order.user.email
            }
        ]
    }

    dynamic_adapter = ConnectAdapter(
        base_url=profile.connect_base_url,
        api_key=api_key_secret
    )

    try:
        result = await dynamic_adapter.submit_order(payload)
        order.sync_status = SyncStatus.synced
        order.connect_ref = result.get("data", {}).get("name") or result.get("name") or str(result)
        order.sync_error = None
        order.sync_retries = 0
        db.commit()
        logger.info("CONNECT sync success — order %s → ref %s", order.order_number, order.connect_ref)
    except Exception as exc:
        order.sync_status = SyncStatus.failed
        order.sync_error = str(exc)[:1000]
        order.sync_retries += 1
        db.add(Alert(
            severity=AlertSeverity.critical,
            alert_type=AlertType.sync_failure,
            title=f"CONNECT sync failed: {order.order_number}",
            message=f"Order {order.order_number} failed to sync to CONNECT: {str(exc)[:500]}",
        ))
        db.commit()
        logger.error("CONNECT sync failed — order %s: %s", order.order_number, exc)


async def sync_order_to_zap(order: Order, db: Session) -> None:
    profile = db.query(CompanyProfile).filter(CompanyProfile.id == order.company_profile_id).first()
    if not profile or not profile.zap_base_url or not profile.zap_api_key_encrypted:
        order.sync_status = SyncStatus.failed
        order.sync_error = "ZAP configuration missing for this company profile."
        db.commit()
        return

    api_key_secret = decrypt(profile.zap_api_key_encrypted)

    zap = ZapAdapter(
        base_url=profile.zap_base_url,
        api_key=api_key_secret,
    )

    # 1. Resolve custom_sales_person (links to User doctype, where name is email)
    sales_person = None
    try:
        res = await zap._request_with_retry("GET", f"/api/resource/User/{order.user.email}")
        if res and res.get("data"):
            sales_person = order.user.email
    except Exception:
        pass

    if not sales_person:
        try:
            res = await zap._request_with_retry("GET", "/api/method/frappe.auth.get_logged_user")
            sales_person = res.get("message")
        except Exception:
            sales_person = "vinodkumarkolli@gmail.com"

    # 2. Determine tax template suffix
    company_name = profile.zap_backend_company or profile.name
    if "Sravi" in company_name or "Kolapakkam" in company_name:
        tax_suffix = "- SE-K"
    elif "Tamizha" in company_name or "Mangalagiri" in company_name:
        tax_suffix = "- THH-M"
    else:
        tax_suffix = "- SE-K"

    items_payload = []
    for it in order.items:
        # Determine tax rate based on product
        tax_rate = int(it.product.gst_rate) if (it.product and it.product.gst_rate) else 12
        if tax_rate not in [5, 12, 18, 28]:
            tax_rate = 12
        item_tax_template = f"GST {tax_rate}% {tax_suffix}"

        items_payload.append({
            "item_code": it.product.sku or it.product.erp_id or it.product.name,
            "qty": it.quantity,
            "rate": float(it.unit_price) if it.unit_price else 10.0, # default if 0/None for testing
            "item_tax_template": item_tax_template
        })

    payload = {
        "naming_series": "SINV-",
        "company": company_name,
        "customer": order.outlet.erp_id or order.outlet.name,
        "posting_date": order.created_at.strftime("%Y-%m-%d") if order.created_at else datetime.now().strftime("%Y-%m-%d"),
        "custom_sales_person": sales_person,
        "items": items_payload,
    }

    try:
        result = await zap.create_sales_invoice(payload)
        order.sync_status = SyncStatus.synced
        order.connect_ref = result.get("data", {}).get("name") or result.get("name") or str(result)[:100]
        order.sync_error = None
        order.sync_retries = 0
        db.commit()
        logger.info("ZAP sync success — order %s → ref %s", order.order_number, order.connect_ref)
    except Exception as exc:
        order.sync_status = SyncStatus.failed
        order.sync_error = str(exc)[:1000]
        order.sync_retries += 1
        db.add(Alert(
            severity=AlertSeverity.critical,
            alert_type=AlertType.sync_failure,
            title=f"ZAP sync failed: {order.order_number}",
            message=f"Order {order.order_number} failed to sync to ZAP: {str(exc)[:500]}",
        ))
        db.commit()
        logger.error("ZAP sync failed — order %s: %s", order.order_number, exc)
