from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.sql import func

from app.models.base import Base


class AuditEvent(Base):
    """Append-only, privacy-preserving record of security-relevant requests."""

    __tablename__ = "audit_events"
    __table_args__ = (
        Index("ix_audit_events_actor_created", "actor_user_id", "created_at"),
        Index("ix_audit_events_route_created", "route", "created_at"),
        Index("ix_audit_events_action_created", "action", "created_at"),
        Index("ix_audit_events_request_id", "request_id"),
    )

    id = Column(Integer, primary_key=True)
    actor_user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    actor_hash = Column(String(64), nullable=True)
    actor_role = Column(String(50), nullable=True)
    ip_hash = Column(String(64), nullable=True)
    action = Column(String(40), nullable=False)
    method = Column(String(10), nullable=False)
    route = Column(String(255), nullable=False)
    object_type = Column(String(100), nullable=True)
    object_id = Column(String(100), nullable=True)
    outcome = Column(String(20), nullable=False)
    status_code = Column(Integer, nullable=False)
    request_id = Column(String(100), nullable=True)
    metadata_json = Column(Text, nullable=False, default="{}")
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
