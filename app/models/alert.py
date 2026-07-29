import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class AlertSeverity(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"


class AlertType(str, enum.Enum):
    missing_checkin = "missing_checkin"
    stale_payment = "stale_payment"
    stale_order = "stale_order"
    sync_failure = "sync_failure"
    custom = "custom"


class Alert(Base):
    __tablename__ = "alerts"

    id = Column(Integer, primary_key=True)
    severity = Column(Enum(AlertSeverity), nullable=False, default=AlertSeverity.info)
    alert_type = Column(Enum(AlertType), nullable=False, default=AlertType.custom)
    title = Column(String(200), nullable=False)
    message = Column(Text, nullable=False)
    is_read = Column(Boolean, nullable=False, default=False)

    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=True, index=True)
    geography_id = Column(Integer, ForeignKey("geographies.id", ondelete="SET NULL"), nullable=True, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True, index=True)

    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id])
    geography = relationship("Geography", foreign_keys=[geography_id])
    vendor = relationship("Vendor", foreign_keys=[vendor_id])

    def severity_badge_cls(self) -> str:
        return {
            AlertSeverity.info: "bg-blue-900/50 text-blue-300",
            AlertSeverity.warning: "bg-amber-900/50 text-amber-300",
            AlertSeverity.critical: "bg-red-900/50 text-red-300",
        }.get(self.severity, "bg-slate-700 text-slate-300")
