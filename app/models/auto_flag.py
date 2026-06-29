"""
Auto-flagging system — Flags suspicious field activity patterns.
GPS > 100m = flagged, visit < 2 min = flagged.
Each flag is visible to admin and can be rated (severity).
"""
import enum

from sqlalchemy import Column, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class FlagType(str, enum.Enum):
    gps_out_of_range = "gps_out_of_range"       # GPS > threshold
    short_visit = "short_visit"                   # Visit < 2 min
    gps_spoofing = "gps_spoofing"                 # Suspicious GPS pattern
    payment_mismatch = "payment_mismatch"         # Denomination != amount
    unusual_activity = "unusual_activity"         # General anomaly


class FlagSeverity(str, enum.Enum):
    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


class FlagStatus(str, enum.Enum):
    open = "open"
    reviewed = "reviewed"
    dismissed = "dismissed"
    escalated = "escalated"


class AutoFlag(Base):
    __tablename__ = "auto_flags"

    id = Column(Integer, primary_key=True)
    flag_type = Column(Enum(FlagType), nullable=False)
    severity = Column(Enum(FlagSeverity), nullable=False, default=FlagSeverity.medium)
    status = Column(Enum(FlagStatus), nullable=False, default=FlagStatus.open)
    # Who was flagged
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # What was flagged (polymorphic reference)
    entity_type = Column(String(50), nullable=False)  # visit_record, payment, order, etc.
    entity_id = Column(Integer, nullable=False)
    # Details
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    metric_value = Column(Float, nullable=True)  # e.g. distance in metres, visit duration in seconds
    threshold_value = Column(Float, nullable=True)  # the threshold that was breached
    # Admin rating / review
    admin_rating = Column(Integer, nullable=True)  # 1-5 severity rating by admin
    reviewed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reviewed_at = Column(DateTime, nullable=True)
    review_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    reviewed_by = relationship("User", foreign_keys=[reviewed_by_id])

    def severity_badge_cls(self) -> str:
        return {
            FlagSeverity.low: "bg-blue-900/50 text-blue-300",
            FlagSeverity.medium: "bg-amber-900/50 text-amber-300",
            FlagSeverity.high: "bg-orange-900/50 text-orange-300",
            FlagSeverity.critical: "bg-red-900/50 text-red-300",
        }.get(self.severity, "bg-slate-700 text-slate-300")

    def status_badge_cls(self) -> str:
        return {
            FlagStatus.open: "bg-red-900/50 text-red-300",
            FlagStatus.reviewed: "bg-blue-900/50 text-blue-300",
            FlagStatus.dismissed: "bg-slate-700 text-slate-400",
            FlagStatus.escalated: "bg-orange-900/50 text-orange-300",
        }.get(self.status, "bg-slate-700 text-slate-300")
