import enum
from datetime import datetime

from sqlalchemy import (Column, DateTime, Enum, ForeignKey, Integer, String,
                        Text, func)
from sqlalchemy.orm import relationship

from app.models.base import Base


class MRStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    acknowledged = "acknowledged"
    in_progress = "in_progress"
    completed = "completed"
    cancelled = "cancelled"


class MRSyncStatus(str, enum.Enum):
    not_applicable = "not_applicable"
    pending = "pending"
    synced = "synced"
    failed = "failed"


class MaterialRequest(Base):
    __tablename__ = "material_requests"

    id = Column(Integer, primary_key=True)
    mr_number = Column(String(30), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="RESTRICT"), nullable=False)
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True)
    category = Column(String(100), nullable=True)
    description = Column(Text, nullable=False)
    status = Column(Enum(MRStatus), nullable=False, default=MRStatus.draft)
    sync_status = Column(Enum(MRSyncStatus), nullable=False, default=MRSyncStatus.not_applicable)
    cmms_ref = Column(String(100), nullable=True)
    cmms_response = Column(Text, nullable=True)
    sync_error = Column(Text, nullable=True)
    sync_retries = Column(Integer, nullable=False, default=0)
    submitted_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="material_requests")
    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    company_profile = relationship("CompanyProfile", foreign_keys=[company_profile_id])

    def status_badge_cls(self) -> str:
        return {
            MRStatus.draft: "bg-slate-700 text-slate-300",
            MRStatus.submitted: "bg-blue-900/50 text-blue-300",
            MRStatus.acknowledged: "bg-indigo-900/50 text-indigo-300",
            MRStatus.in_progress: "bg-amber-900/50 text-amber-300",
            MRStatus.completed: "bg-emerald-900/50 text-emerald-300",
            MRStatus.cancelled: "bg-red-900/50 text-red-300",
        }.get(self.status, "bg-slate-700 text-slate-300")

    def sync_badge_cls(self) -> str:
        return {
            MRSyncStatus.not_applicable: "bg-slate-700 text-slate-400",
            MRSyncStatus.pending: "bg-amber-900/50 text-amber-300",
            MRSyncStatus.synced: "bg-emerald-900/50 text-emerald-300",
            MRSyncStatus.failed: "bg-red-900/50 text-red-300",
        }.get(self.sync_status, "bg-slate-700 text-slate-300")
