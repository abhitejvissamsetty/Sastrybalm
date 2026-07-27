"""
Attendance model — Separate from Timesheet.
1 Attendance can be mapped to multiple Timesheet records (within same date).
Auto-calculates attendance type based on hours comparison.
"""
import enum

from sqlalchemy import Boolean, Column, Date, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ApprovalStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class AttendanceType(str, enum.Enum):
    full_day = "full_day"
    half_day = "half_day"
    absent = "absent"


class Attendance(Base):
    __tablename__ = "attendance"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True)
    date = Column(Date, nullable=False, index=True)
    checkin_time = Column(DateTime, nullable=True)
    checkout_time = Column(DateTime, nullable=True)
    # Calculated hours
    total_hours = Column(Float, nullable=True)          # checkout - checkin
    timesheet_hours = Column(Float, nullable=True)      # sum of timesheet hours
    activity_hours = Column(Float, nullable=True)       # activity-based calculation
    # Attendance determination
    attendance_type = Column(Enum(AttendanceType), nullable=True)
    suggested_type = Column(Enum(AttendanceType), nullable=True)
    # Approval
    approval_status = Column(Enum(ApprovalStatus), nullable=False, default=ApprovalStatus.pending)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    user = relationship("User", foreign_keys=[user_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])

    def approval_badge_cls(self) -> str:
        return {
            ApprovalStatus.pending: "bg-amber-900/50 text-amber-300",
            ApprovalStatus.approved: "bg-emerald-900/50 text-emerald-300",
            ApprovalStatus.rejected: "bg-red-900/50 text-red-300",
        }.get(self.approval_status, "bg-slate-700 text-slate-300")

    def type_badge_cls(self) -> str:
        return {
            AttendanceType.full_day: "bg-emerald-900/50 text-emerald-300",
            AttendanceType.half_day: "bg-amber-900/50 text-amber-300",
            AttendanceType.absent: "bg-red-900/50 text-red-300",
        }.get(self.attendance_type, "bg-slate-700 text-slate-300")

    @property
    def punch_in(self):
        return self.checkin_time

    @property
    def punch_out(self):
        return self.checkout_time

    @property
    def type_display(self) -> str:
        if self.attendance_type:
            return self.attendance_type.value.replace("_", " ").title()
        return "—"
