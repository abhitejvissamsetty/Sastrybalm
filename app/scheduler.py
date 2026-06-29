"""
APScheduler background jobs for Sastrybalm SFA.
Started via FastAPI lifespan in main.py.
"""
from datetime import date, datetime, timedelta

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.timesheet import Timesheet
from app.models.user import User, UserRole

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def _get_db():
    db = SessionLocal()
    try:
        return db
    except Exception:
        db.close()
        raise


def _alert_exists(db, alert_type: AlertType, title: str, since: datetime) -> bool:
    return db.query(Alert).filter(
        Alert.alert_type == alert_type,
        Alert.title == title,
        Alert.created_at >= since,
    ).first() is not None


def job_missing_checkins() -> None:
    """Raise a warning for every active field rep with no check-in today."""
    db = SessionLocal()
    try:
        today = date.today()
        active_reps = (
            db.query(User)
            .filter(User.role == UserRole.field_rep, User.is_active == True)
            .all()
        )
        reps_checked_in = {
            ts.user_id
            for ts in db.query(Timesheet).filter(Timesheet.work_date == today).all()
        }
        since_midnight = datetime.combine(today, datetime.min.time())
        missing = [r for r in active_reps if r.id not in reps_checked_in]
        for rep in missing:
            title = f"No check-in: {rep.full_name}"
            if not _alert_exists(db, AlertType.missing_checkin, title, since_midnight):
                db.add(Alert(
                    severity=AlertSeverity.warning,
                    alert_type=AlertType.missing_checkin,
                    title=title,
                    message=(
                        f"{rep.full_name} has not checked in today ({today}). "
                        "Verify attendance with the rep."
                    ),
                ))
        db.commit()
    finally:
        db.close()


def job_stale_payments() -> None:
    """Alert on collected payments that have been sitting unverified for > 24h."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=24)
        stale = (
            db.query(Payment)
            .filter(
                Payment.status == PaymentStatus.collected,
                Payment.created_at <= cutoff,
            )
            .all()
        )
        since_1h = datetime.utcnow() - timedelta(hours=1)
        for p in stale:
            title = f"Unverified payment: {p.payment_ref}"
            if not _alert_exists(db, AlertType.stale_payment, title, since_1h):
                db.add(Alert(
                    severity=AlertSeverity.warning,
                    alert_type=AlertType.stale_payment,
                    title=title,
                    message=(
                        f"Payment {p.payment_ref} (₹{p.amount}) has been collected "
                        f"but not verified for over 24 hours. Please review."
                    ),
                ))
        db.commit()
    finally:
        db.close()


def job_stale_orders() -> None:
    """Alert on submitted orders not confirmed within 48h."""
    db = SessionLocal()
    try:
        cutoff = datetime.utcnow() - timedelta(hours=48)
        stale = (
            db.query(Order)
            .filter(
                Order.status == OrderStatus.submitted,
                Order.created_at <= cutoff,
            )
            .all()
        )
        since_1h = datetime.utcnow() - timedelta(hours=1)
        for o in stale:
            title = f"Unconfirmed order: {o.order_number}"
            if not _alert_exists(db, AlertType.stale_order, title, since_1h):
                db.add(Alert(
                    severity=AlertSeverity.critical,
                    alert_type=AlertType.stale_order,
                    title=title,
                    message=(
                        f"Order {o.order_number} was submitted over 48 hours ago "
                        f"and is still pending confirmation. Please action immediately."
                    ),
                ))
        db.commit()
    finally:
        db.close()


def job_retry_failed_syncs() -> None:
    """Auto-retry material requests, asset capitalizations, and orders with failed sync status (max 3 auto-retries)."""
    import asyncio
    import json
    from datetime import datetime, timedelta

    from app.adapters.cmms import CMSAdapter
    from app.adapters.connect import ConnectAdapter
    from app.models.company import CompanyProfile
    from app.models.material_request import MaterialRequest, MRSyncStatus
    from app.models.asset_capitalization import AssetCapitalization, ACSyncStatus
    from app.models.order import FlowType, SyncStatus
    from app.models.product import Product
    from app.models.product_mapping import ProductAliasMap, AccountAliasMap
    from app.utils.encryption import decrypt
    from app.models.alert import Alert, AlertSeverity, AlertType

    db = SessionLocal()
    try:
        # Retry failed material requests
        failed_mrs = (
            db.query(MaterialRequest)
            .filter(
                MaterialRequest.sync_status == MRSyncStatus.failed,
                MaterialRequest.sync_retries < 3,
            )
            .all()
        )
        for mr in failed_mrs:
            profile = db.query(CompanyProfile).filter(CompanyProfile.id == mr.company_profile_id).first()
            if not profile or not profile.cmms_base_url:
                mr.sync_error = "CMMS configuration missing for this company profile."
                mr.sync_retries += 1
                continue

            api_key_secret = decrypt(profile.cmms_api_key_encrypted)

            # 1. Resolve custom_location
            custom_location = "Test Location"
            if mr.outlet:
                if mr.outlet.territory:
                    custom_location = mr.outlet.territory.name
                else:
                    custom_location = mr.outlet.name

            # 2. Resolve items.item_code dynamically
            cmms_item_code = "MBLIT"
            if mr.category:
                product = db.query(Product).filter(
                    (Product.sku == mr.category) | 
                    (Product.erp_id == mr.category) | 
                    (Product.name == mr.category)
                ).first()
                if product:
                    alias = db.query(ProductAliasMap).filter(
                        ProductAliasMap.company_profile_id == mr.company_profile_id,
                        ProductAliasMap.product_id == product.id
                    ).first()
                    if alias and alias.cmms_item_code:
                        cmms_item_code = alias.cmms_item_code
                    else:
                        cmms_item_code = product.sku or product.erp_id or cmms_item_code
                else:
                    cmms_item_code = mr.category

            # 3. Resolve warehouse, expense_account, cost_center dynamically
            warehouse_alias = db.query(AccountAliasMap).filter(
                AccountAliasMap.company_profile_id == mr.company_profile_id,
                AccountAliasMap.account_name == "warehouse"
            ).first()
            warehouse = warehouse_alias.cmms_account_code if warehouse_alias else f"Stores - {profile.code}"

            expense_alias = db.query(AccountAliasMap).filter(
                AccountAliasMap.company_profile_id == mr.company_profile_id,
                AccountAliasMap.account_name == "expense_account"
            ).first()
            expense_account = expense_alias.cmms_account_code if expense_alias else f"Capital Equipment - {profile.code}"

            cost_center_alias = db.query(AccountAliasMap).filter(
                AccountAliasMap.company_profile_id == mr.company_profile_id,
                AccountAliasMap.account_name == "cost_center"
            ).first()
            cost_center = cost_center_alias.cmms_account_code if cost_center_alias else f"Main - {profile.code}"

            # Build the items list
            schedule_date = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")
            items_payload = [
                {
                    "item_code": cmms_item_code,
                    "qty": 1,
                    "custom_request_description": mr.description,
                    "schedule_date": schedule_date,
                    "warehouse": warehouse,
                    "uom": "Nos",
                    "expense_account": expense_account,
                    "cost_center": cost_center
                }
            ]

            payload = {
                "material_request_type": "Purchase",
                "company": profile.cmms_backend_company or profile.name,
                "custom_location": custom_location,
                "custom_raised_by": mr.user.email if mr.user else "N/A",
                "items": items_payload
            }

            dynamic_adapter = CMSAdapter(
                base_url=profile.cmms_base_url,
                api_key=api_key_secret
            )

            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                result = loop.run_until_complete(dynamic_adapter.create_material_request(payload))
                mr.sync_status = MRSyncStatus.synced
                mr.cmms_ref = result.get("name") or result.get("id") or str(result)
                mr.cmms_response = json.dumps(result)[:2000]
                mr.sync_error = None
                mr.sync_retries = 0
            except Exception as exc:
                mr.sync_retries += 1
                mr.sync_error = str(exc)[:1000]
                if mr.sync_retries >= 3:
                    db.add(Alert(
                        severity=AlertSeverity.critical,
                        alert_type=AlertType.sync_failure,
                        title=f"CMMS sync exhausted retries: {mr.mr_number}",
                        message=f"Auto-retry exhausted after 3 attempts: {str(exc)[:500]}",
                    ))

        # Retry failed asset capitalizations
        failed_acs = (
            db.query(AssetCapitalization)
            .filter(
                AssetCapitalization.sync_status == ACSyncStatus.failed,
                AssetCapitalization.sync_retries < 3,
            )
            .all()
        )
        for ac in failed_acs:
            profile = db.query(CompanyProfile).filter(CompanyProfile.id == ac.company_profile_id).first()
            if not profile or not profile.cmms_base_url:
                ac.sync_error = "CMMS configuration missing for this company profile."
                ac.sync_retries += 1
                continue

            api_key_secret = decrypt(profile.cmms_api_key_encrypted)

            # 1. Resolve target_item_code
            target_item_code = "MBLIT"
            if ac.item_code:
                target_item_code = ac.item_code
            elif ac.item_name:
                product = db.query(Product).filter(
                    (Product.sku == ac.item_name) | 
                    (Product.erp_id == ac.item_name) | 
                    (Product.name == ac.item_name)
                ).first()
                if product:
                    alias = db.query(ProductAliasMap).filter(
                        ProductAliasMap.company_profile_id == ac.company_profile_id,
                        ProductAliasMap.product_id == product.id
                    ).first()
                    if alias and alias.cmms_item_code:
                        target_item_code = alias.cmms_item_code
                    else:
                        target_item_code = product.sku or product.erp_id or target_item_code
                else:
                    target_item_code = ac.item_name

            # 2. Resolve target_asset_location
            target_asset_location = "Test Location"
            if ac.outlet:
                if ac.outlet.territory:
                    target_asset_location = ac.outlet.territory.name
                else:
                    target_asset_location = ac.outlet.name

            # 3. Resolve service items & accounts
            service_item_code = "Installation Service"
            svc_prod = db.query(Product).filter(
                (Product.name == "Installation Service") | 
                (Product.erp_id == "Installation Service")
            ).first()
            if svc_prod:
                alias = db.query(ProductAliasMap).filter(
                    ProductAliasMap.company_profile_id == ac.company_profile_id,
                    ProductAliasMap.product_id == svc_prod.id
                ).first()
                if alias and alias.cmms_item_code:
                    service_item_code = alias.cmms_item_code

            expense_alias = db.query(AccountAliasMap).filter(
                AccountAliasMap.company_profile_id == ac.company_profile_id,
                AccountAliasMap.account_name == "expense_account"
            ).first()
            expense_account = expense_alias.cmms_account_code if expense_alias else f"Capital Equipment - {profile.code}"

            cost_center_alias = db.query(AccountAliasMap).filter(
                AccountAliasMap.company_profile_id == ac.company_profile_id,
                AccountAliasMap.account_name == "cost_center"
            ).first()
            cost_center = cost_center_alias.cmms_account_code if cost_center_alias else f"Main - {profile.code}"

            service_items = [
                {
                    "item_code": service_item_code,
                    "qty": 1,
                    "uom": "Nos",
                    "rate": 100.0,
                    "expense_account": expense_account,
                    "cost_center": cost_center
                }
            ]

            posting_date = (ac.deployed_at or datetime.now()).strftime("%Y-%m-%d")

            payload = {
                "company": profile.cmms_backend_company or profile.name,
                "target_item_code": target_item_code,
                "target_asset_location": target_asset_location,
                "posting_date": posting_date,
                "service_items": service_items,
                "custom_installation_notes": ac.notes or "Asset deployed by Sastrybalm rep",
                "custom_installation_photo_1": "",
                "custom_installation_length": 8,
                "custom_installation_height": 5,
                "custom_installation_depth": 0.8
            }

            dynamic_adapter = CMSAdapter(
                base_url=profile.cmms_base_url,
                api_key=api_key_secret
            )

            try:
                try:
                    loop = asyncio.get_event_loop()
                except RuntimeError:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                result = loop.run_until_complete(dynamic_adapter.create_asset_capitalization(payload))
                ac.sync_status = ACSyncStatus.synced
                ac.cmms_ref = result.get("name") or result.get("id") or str(result)[:100]
                ac.sync_error = None
                ac.sync_retries = 0
            except Exception as exc:
                ac.sync_retries += 1
                ac.sync_error = str(exc)[:1000]
                if ac.sync_retries >= 3:
                    db.add(Alert(
                        severity=AlertSeverity.critical,
                        alert_type=AlertType.sync_failure,
                        title=f"CMMS AC sync exhausted retries: {ac.ac_number}",
                        message=f"Auto-retry exhausted after 3 attempts: {str(exc)[:500]}",
                    ))

        # Retry failed CONNECT orders
        failed_orders = (
            db.query(Order)
            .filter(
                Order.flow_type == FlowType.connect,
                Order.sync_status == SyncStatus.failed,
                Order.sync_retries < 3,
            )
            .all()
        )
        for order in failed_orders:
            profile = db.query(CompanyProfile).filter(CompanyProfile.id == order.company_profile_id).first()
            if not profile or not profile.connect_base_url:
                order.sync_error = "CONNECT configuration missing for this company profile."
                order.sync_retries += 1
                continue

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
                loop = asyncio.get_event_loop()
                result = loop.run_until_complete(dynamic_adapter.submit_order(payload))
                order.sync_status = SyncStatus.synced
                order.connect_ref = result.get("data", {}).get("name") or result.get("name") or str(result)
                order.sync_error = None
            except Exception as exc:
                order.sync_retries += 1
                order.sync_error = str(exc)[:1000]
                if order.sync_retries >= 3:
                    db.add(Alert(
                        severity=AlertSeverity.critical,
                        alert_type=AlertType.sync_failure,
                        title=f"CONNECT sync exhausted retries: {order.order_number}",
                        message=f"Auto-retry exhausted after 3 attempts: {str(exc)[:500]}",
                    ))

        db.commit()
    finally:
        db.close()


def start_scheduler() -> None:
    # Missing check-in alert at 10:30 AM IST on weekdays
    scheduler.add_job(
        job_missing_checkins,
        CronTrigger(hour=10, minute=30, day_of_week="mon-sat"),
        id="missing_checkins",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Stale payment + order checks at 9 PM IST daily
    scheduler.add_job(
        job_stale_payments,
        CronTrigger(hour=21, minute=0),
        id="stale_payments",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.add_job(
        job_stale_orders,
        CronTrigger(hour=21, minute=5),
        id="stale_orders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Retry failed CMMS/CONNECT syncs every 30 minutes
    scheduler.add_job(
        job_retry_failed_syncs,
        CronTrigger(minute="*/30"),
        id="retry_failed_syncs",
        replace_existing=True,
        misfire_grace_time=1800,
    )
    scheduler.start()
