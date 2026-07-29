from datetime import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, UniqueConstraint

from app.models.base import Base


class SchedulerHeartbeat(Base):
    __tablename__ = "scheduler_heartbeats"

    id = Column(Integer, primary_key=True, default=1)
    owner_id = Column(String(255), nullable=False)
    acquired_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    heartbeat_at = Column(DateTime, nullable=False, default=datetime.utcnow, index=True)


class SchedulerJobRun(Base):
    __tablename__ = "scheduler_job_runs"
    __table_args__ = (
        UniqueConstraint(
            "job_name", "scheduled_bucket",
            name="uq_scheduler_job_run_name_bucket",
        ),
    )

    id = Column(Integer, primary_key=True)
    job_name = Column(String(100), nullable=False, index=True)
    scheduled_bucket = Column(DateTime, nullable=False)
    status = Column(String(20), nullable=False, default="running", index=True)
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    error = Column(Text, nullable=True)


class NotificationDelivery(Base):
    __tablename__ = "notification_deliveries"
    __table_args__ = (
        UniqueConstraint(
            "event_type",
            "entity_type",
            "entity_id",
            "recipient_type",
            "recipient_id",
            name="uq_notification_delivery_event_recipient",
        ),
    )

    id = Column(Integer, primary_key=True)
    event_type = Column(String(100), nullable=False)
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(Integer, nullable=False)
    recipient_type = Column(String(50), nullable=False)
    recipient_id = Column(Integer, nullable=False)
    status = Column(String(20), nullable=False, default="sent")
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
