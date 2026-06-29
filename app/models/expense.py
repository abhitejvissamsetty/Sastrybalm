import enum
from datetime import date, datetime

from sqlalchemy import (Column, Date, DateTime, Enum, ForeignKey, Integer,
                        Numeric, String, Text, func)
from sqlalchemy.orm import relationship

from app.models.base import Base


class ExpenseCategory(str, enum.Enum):
    travel = "travel"
    food = "food"
    accommodation = "accommodation"
    communication = "communication"
    other = "other"


class ExpenseStatus(str, enum.Enum):
    draft = "draft"
    submitted = "submitted"
    approved = "approved"
    rejected = "rejected"


class Expense(Base):
    __tablename__ = "expenses"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    category = Column(Enum(ExpenseCategory), nullable=False)
    amount = Column(Numeric(10, 2), nullable=False)
    description = Column(Text, nullable=True)
    expense_date = Column(Date, nullable=False, default=date.today)
    receipt_url = Column(String(500), nullable=True)
    status = Column(Enum(ExpenseStatus), nullable=False, default=ExpenseStatus.draft)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    user = relationship("User", foreign_keys=[user_id], back_populates="expenses")
    approved_by = relationship("User", foreign_keys=[approved_by_id])

    def status_badge_cls(self) -> str:
        return {
            ExpenseStatus.draft: "bg-slate-700 text-slate-300",
            ExpenseStatus.submitted: "bg-blue-900/50 text-blue-300",
            ExpenseStatus.approved: "bg-emerald-900/50 text-emerald-300",
            ExpenseStatus.rejected: "bg-red-900/50 text-red-300",
        }.get(self.status, "bg-slate-700 text-slate-300")
