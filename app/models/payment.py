import enum
from datetime import datetime

from sqlalchemy import (Column, DateTime, Enum, ForeignKey, Integer, Numeric,
                        String, Text, func)
from sqlalchemy.orm import relationship

from app.models.base import Base


class PaymentMethod(str, enum.Enum):
    cash = "cash"
    upi = "upi"
    cheque = "cheque"
    neft = "neft"


class PaymentStatus(str, enum.Enum):
    pending = "pending"
    collected = "collected"
    verified = "verified"
    rejected = "rejected"


class PaymentType(str, enum.Enum):
    invoice_payment = "invoice_payment"
    advance = "advance"
    credit_note = "credit_note"


class Payment(Base):
    __tablename__ = "payments"

    id = Column(Integer, primary_key=True)
    payment_ref = Column(String(50), unique=True, nullable=False, index=True)
    order_id = Column(Integer, ForeignKey("orders.id", ondelete="SET NULL"), nullable=True)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="RESTRICT"), nullable=False)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    amount = Column(Numeric(12, 2), nullable=False)
    method = Column(Enum(PaymentMethod), nullable=False, default=PaymentMethod.cash)
    payment_type = Column(Enum(PaymentType), nullable=False, default=PaymentType.invoice_payment)
    transaction_ref = Column(String(100), nullable=True)
    status = Column(Enum(PaymentStatus), nullable=False, default=PaymentStatus.pending)
    # Cash denomination breakdown (for denomination_mandatory mode)
    denom_2000 = Column(Integer, nullable=False, default=0)
    denom_500 = Column(Integer, nullable=False, default=0)
    denom_200 = Column(Integer, nullable=False, default=0)
    denom_100 = Column(Integer, nullable=False, default=0)
    denom_50 = Column(Integer, nullable=False, default=0)
    denom_20 = Column(Integer, nullable=False, default=0)
    denom_10 = Column(Integer, nullable=False, default=0)
    # Submission tracking
    submission_id = Column(Integer, ForeignKey("payment_submissions.id", ondelete="SET NULL"), nullable=True)
    collected_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    order = relationship("Order", back_populates="payments")
    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    user = relationship("User", foreign_keys=[user_id], back_populates="payments")
    submission = relationship("PaymentSubmission", back_populates="payment_items", foreign_keys=[submission_id])

    @property
    def denomination_total(self) -> int:
        return (
            self.denom_2000 * 2000 + self.denom_500 * 500 + self.denom_200 * 200
            + self.denom_100 * 100 + self.denom_50 * 50
            + self.denom_20 * 20 + self.denom_10 * 10
        )

    def status_badge_cls(self) -> str:
        return {
            PaymentStatus.pending: "bg-amber-900/50 text-amber-300",
            PaymentStatus.collected: "bg-blue-900/50 text-blue-300",
            PaymentStatus.verified: "bg-emerald-900/50 text-emerald-300",
            PaymentStatus.rejected: "bg-red-900/50 text-red-300",
        }.get(self.status, "bg-slate-700 text-slate-300")

    def type_badge_cls(self) -> str:
        return {
            PaymentType.invoice_payment: "bg-indigo-900/50 text-indigo-300",
            PaymentType.advance: "bg-cyan-900/50 text-cyan-300",
            PaymentType.credit_note: "bg-orange-900/50 text-orange-300",
        }.get(self.payment_type, "bg-slate-700 text-slate-300")
