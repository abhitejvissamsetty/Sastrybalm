from __future__ import annotations
import enum
from datetime import date, datetime

from sqlalchemy import (Boolean, Column, Date, DateTime, Enum, Float, ForeignKey,
                        Integer, String, Text, func)
from sqlalchemy.orm import relationship

from app.models.base import Base


class TimesheetStatus(str, enum.Enum):
    open = "open"
    closed = "closed"


class TimesheetApproval(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"


class Timesheet(Base):
    __tablename__ = "timesheets"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    attendance_id = Column(Integer, ForeignKey("attendance.id", ondelete="SET NULL"), nullable=True)
    work_date = Column(Date, nullable=False, default=date.today)
    checkin_time = Column(DateTime, nullable=True)
    checkout_time = Column(DateTime, nullable=True)
    checkin_lat = Column(Float, nullable=True)
    checkin_lng = Column(Float, nullable=True)
    checkout_lat = Column(Float, nullable=True)
    checkout_lng = Column(Float, nullable=True)
    checkin_address = Column(String(300), nullable=True)
    checkout_address = Column(String(300), nullable=True)
    status = Column(Enum(TimesheetStatus), nullable=False, default=TimesheetStatus.open)
    # Approval workflow
    approval_status = Column(Enum(TimesheetApproval), nullable=False, default=TimesheetApproval.pending)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    activity_type = Column(String(100), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="timesheets")
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    attendance = relationship("Attendance", foreign_keys=[attendance_id])
    visits = relationship("VisitRecord", back_populates="timesheet")

    @property
    def hours_worked(self) -> float | None:
        if self.checkin_time and self.checkout_time:
            delta = self.checkout_time - self.checkin_time
            return round(delta.total_seconds() / 3600, 2)
        return None

    @property
    def visit_count(self) -> int:
        return len(self.visits)

    def approval_badge_cls(self) -> str:
        return {
            TimesheetApproval.pending: "bg-amber-900/50 text-amber-300",
            TimesheetApproval.approved: "bg-emerald-900/50 text-emerald-300",
            TimesheetApproval.rejected: "bg-red-900/50 text-red-300",
        }.get(self.approval_status, "bg-slate-700 text-slate-300")


class VisitRecord(Base):
    __tablename__ = "visit_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="RESTRICT"), nullable=False)
    timesheet_id = Column(Integer, ForeignKey("timesheets.id", ondelete="SET NULL"), nullable=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    visit_time = Column(DateTime, nullable=False, server_default=func.now())
    checkout_time = Column(DateTime, nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    distance_from_outlet = Column(Float, nullable=True)
    purpose = Column(String(50), nullable=True)
    visit_type = Column(String(30), nullable=True)  # in_location, telephonic, out_of_range
    notes = Column(Text, nullable=True)
    # Joint Working fields
    is_joint_visit = Column(Boolean, default=False, nullable=False)
    joint_with_user_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    joint_with_name = Column(String(255), nullable=True)
    joint_with_role = Column(String(100), nullable=True)
    joint_notes = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    joint_with_user = relationship("User", foreign_keys=[joint_with_user_id])
    user = relationship("User", foreign_keys=[user_id], back_populates="visit_records")
    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    timesheet = relationship("Timesheet", back_populates="visits")
    order = relationship("Order", foreign_keys=[order_id])

    @property
    def duration_minutes(self) -> float | None:
        if self.visit_time and self.checkout_time:
            return round((self.checkout_time - self.visit_time).total_seconds() / 60, 1)
        return None
