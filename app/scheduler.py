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


def start_scheduler() -> None:
    """Start background scheduler for missing check-in, SLA alerts, and daily backups."""
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
    # Automated daily system backup at midnight (00:00 IST)
    scheduler.add_job(
        job_daily_backup,
        CronTrigger(hour=0, minute=0),
        id="daily_backup",
        replace_existing=True,
        misfire_grace_time=3600,
    )
    scheduler.start()
    logger.info("SFA Background Scheduler started successfully.")
