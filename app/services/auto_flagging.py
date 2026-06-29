"""
Auto-flagging service — Detects suspicious field activity patterns.
Thresholds: GPS > 100m flagged, visit < 2 min flagged.
Each flag is visible to admin and can be rated.
"""
from __future__ import annotations
import logging
from datetime import datetime

from sqlalchemy.orm import Session

from app.models.auto_flag import AutoFlag, FlagSeverity, FlagStatus, FlagType
from app.models.company import SystemConfiguration
from app.models.timesheet import VisitRecord

logger = logging.getLogger(__name__)


def get_thresholds(db: Session) -> dict:
    """Fetch flagging thresholds from system configuration."""
    config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    return {
        "gps_distance_metres": config.flag_gps_distance_metres if config else 100,
        "min_visit_seconds": config.flag_min_visit_seconds if config else 120,
    }


def flag_visit_gps(db: Session, visit: VisitRecord) -> AutoFlag | None:
    """Flag a visit if GPS distance from outlet exceeds threshold."""
    thresholds = get_thresholds(db)
    threshold = thresholds["gps_distance_metres"]

    if visit.distance_from_outlet is None:
        return None
    if visit.distance_from_outlet <= threshold:
        return None

    # Check if already flagged
    existing = db.query(AutoFlag).filter(
        AutoFlag.entity_type == "visit_record",
        AutoFlag.entity_id == visit.id,
        AutoFlag.flag_type == FlagType.gps_out_of_range,
    ).first()
    if existing:
        return existing

    severity = FlagSeverity.medium
    if visit.distance_from_outlet > threshold * 3:
        severity = FlagSeverity.critical
    elif visit.distance_from_outlet > threshold * 2:
        severity = FlagSeverity.high

    outlet_name = visit.outlet.name if visit.outlet else f"Outlet #{visit.outlet_id}"
    flag = AutoFlag(
        flag_type=FlagType.gps_out_of_range,
        severity=severity,
        user_id=visit.user_id,
        entity_type="visit_record",
        entity_id=visit.id,
        title=f"GPS out of range: {outlet_name}",
        description=(
            f"Visit to {outlet_name} recorded at {visit.distance_from_outlet:.0f}m "
            f"from outlet location (threshold: {threshold}m)."
        ),
        metric_value=visit.distance_from_outlet,
        threshold_value=float(threshold),
    )
    db.add(flag)
    return flag


def flag_visit_duration(db: Session, visit: VisitRecord) -> AutoFlag | None:
    """Flag a visit if duration is less than minimum threshold."""
    thresholds = get_thresholds(db)
    min_seconds = thresholds["min_visit_seconds"]

    if visit.duration_minutes is None:
        return None

    duration_seconds = visit.duration_minutes * 60
    if duration_seconds >= min_seconds:
        return None

    # Check if already flagged
    existing = db.query(AutoFlag).filter(
        AutoFlag.entity_type == "visit_record",
        AutoFlag.entity_id == visit.id,
        AutoFlag.flag_type == FlagType.short_visit,
    ).first()
    if existing:
        return existing

    severity = FlagSeverity.medium
    if duration_seconds < 30:
        severity = FlagSeverity.critical
    elif duration_seconds < 60:
        severity = FlagSeverity.high

    outlet_name = visit.outlet.name if visit.outlet else f"Outlet #{visit.outlet_id}"
    flag = AutoFlag(
        flag_type=FlagType.short_visit,
        severity=severity,
        user_id=visit.user_id,
        entity_type="visit_record",
        entity_id=visit.id,
        title=f"Short visit: {outlet_name}",
        description=(
            f"Visit to {outlet_name} lasted only {visit.duration_minutes:.1f} minutes "
            f"(minimum: {min_seconds / 60:.0f} min)."
        ),
        metric_value=duration_seconds,
        threshold_value=float(min_seconds),
    )
    db.add(flag)
    return flag


def flag_payment_mismatch(db, payment) -> AutoFlag | None:
    """Flag a payment if denomination total doesn't match amount (cash payments)."""
    from app.models.payment import PaymentMethod

    if payment.method != PaymentMethod.cash:
        return None
    if payment.denomination_total == 0:
        return None  # denominations not filled

    diff = abs(float(payment.amount) - payment.denomination_total)
    if diff < 1:  # tolerance of ₹1
        return None

    existing = db.query(AutoFlag).filter(
        AutoFlag.entity_type == "payment",
        AutoFlag.entity_id == payment.id,
        AutoFlag.flag_type == FlagType.payment_mismatch,
    ).first()
    if existing:
        return existing

    flag = AutoFlag(
        flag_type=FlagType.payment_mismatch,
        severity=FlagSeverity.high,
        user_id=payment.user_id,
        entity_type="payment",
        entity_id=payment.id,
        title=f"Payment denomination mismatch: {payment.payment_ref}",
        description=(
            f"Payment {payment.payment_ref}: amount ₹{payment.amount} but "
            f"denomination total ₹{payment.denomination_total} (diff: ₹{diff:.2f})."
        ),
        metric_value=diff,
        threshold_value=1.0,
    )
    db.add(flag)
    return flag


def check_visit_flags(db: Session, visit: VisitRecord) -> list[AutoFlag]:
    """Run all visit-related flagging checks."""
    flags = []
    f1 = flag_visit_gps(db, visit)
    if f1:
        flags.append(f1)
    f2 = flag_visit_duration(db, visit)
    if f2:
        flags.append(f2)
    return flags
