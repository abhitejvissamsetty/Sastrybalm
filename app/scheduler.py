"""
APScheduler background jobs for Sastrybalm SFA.
Started via FastAPI lifespan in main.py.
Handles field tracking alerts, payment verification reminders, and order SLAs.
"""
from datetime import date, datetime, timedelta
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from app.database import SessionLocal
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.timesheet import Timesheet
from app.models.user import User, UserRole

logger = logging.getLogger(__name__)

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
    """Raise a warning alert for every active field rep with no check-in today."""
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


def job_daily_backup() -> None:
    """Automated daily full system data backup."""
    try:
        from app.utils.backup_service import create_full_system_backup
        filepath = create_full_system_backup()
        logger.info("Automated daily backup created: %s", filepath)
    except Exception as e:
        logger.error("Automated daily backup failed: %s", e)


def job_daily_parquet_backup() -> None:
    """Automated daily rolling Parquet backup of transactional/operational data to Permanent Files Bucket."""
    db = SessionLocal()
    try:
        from app.utils.s3_service import get_s3_config, test_s3_connection
        config = get_s3_config(db)
        if not config.get("s3_is_enabled"):
            logger.info("[SCHEDULER] Skipping daily Parquet rolling backup because Permanent S3 Bucket is not enabled.")
            return

        s3_ok, s3_msg = test_s3_connection(config, bucket_type="permanent")
        if not s3_ok:
            logger.warning(f"[SCHEDULER] Skipping daily Parquet rolling backup because Permanent S3 Bucket connection failed: {s3_msg}")
            return

        from app.services.parquet_backup_service import run_daily_parquet_rolling_backup
        res = run_daily_parquet_rolling_backup(db)
        logger.info(f"Automated daily Parquet rolling backup complete: {res.get('total_tables')} tables, {res.get('total_records')} records exported.")
    except Exception as e:
        logger.error(f"Automated daily Parquet rolling backup failed: {e}")
    finally:
        db.close()


def job_auto_approve_orders() -> None:
    """
    Auto-approves submitted orders that have exceeded the auto-approval cutoff time window
    (configured via SystemConfiguration.auto_approval_cutoff_hours).
    Post-approval, triggers instant notification to the allocated Channel Partner.
    """
    db = SessionLocal()
    try:
        from app.models.company import SystemConfiguration
        sys_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
        cutoff_hours = sys_config.auto_approval_cutoff_hours if sys_config else 24

        cutoff_time = datetime.utcnow() - timedelta(hours=cutoff_hours)
        pending_orders = (
            db.query(Order)
            .filter(
                Order.status == OrderStatus.submitted,
                Order.created_at <= cutoff_time,
            )
            .all()
        )

        from app.services.channel_partner_notification import (
            record_order_history_log,
            trigger_instant_order_notification,
        )

        for o in pending_orders:
            old_st = o.status.value
            o.status = OrderStatus.confirmed
            db.commit()
            logger.info(
                f"[Auto-Approval Scheduler] Order {o.order_number} auto-approved after cutoff window ({cutoff_hours}h)."
            )

            # Audit log entry
            record_order_history_log(
                db=db,
                order_id=o.id,
                action="auto_approved_cutoff",
                performed_by_id=None,
                old_status=old_st,
                new_status=OrderStatus.confirmed.value,
                channel_partner_id=o.channel_partner_id,
                notes=f"Auto-approved by System Scheduler post {cutoff_hours}-hour cutoff window."
            )

            # Trigger notification to allocated Channel Partner
            trigger_instant_order_notification(db, o)

    except Exception as exc:
        logger.error(f"Error in job_auto_approve_orders: {exc}")
    finally:
        db.close()


def start_scheduler() -> None:
    """Start background scheduler for missing check-in, SLA alerts, auto-approvals, and daily backups."""
    # Missing check-in alert at 10:30 AM IST on working days
    scheduler.add_job(
        job_missing_checkins,
        CronTrigger(hour=10, minute=30, day_of_week="mon-sat"),
        id="missing_checkins",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Stale payment alerts at 9 PM IST daily
    scheduler.add_job(
        job_stale_payments,
        CronTrigger(hour=21, minute=0),
        id="stale_payments",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Stale order SLA alerts at 9:05 PM IST daily
    scheduler.add_job(
        job_stale_orders,
        CronTrigger(hour=21, minute=5),
        id="stale_orders",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Auto-approve orders post cutoff time (runs every 15 minutes)
    scheduler.add_job(
        job_auto_approve_orders,
        CronTrigger(minute="*/15"),
        id="auto_approve_orders",
        replace_existing=True,
        misfire_grace_time=600,
    )
    # Automated daily system backup at midnight (00:00 IST)
    scheduler.add_job(
        job_daily_backup,
        CronTrigger(hour=0, minute=0),
        id="daily_backup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    # Automated daily rolling Parquet backup to Permanent Files Bucket at 01:00 AM IST
    scheduler.add_job(
        job_daily_parquet_backup,
        CronTrigger(hour=1, minute=0),
        id="daily_parquet_backup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("SFA Background Scheduler started successfully.")
