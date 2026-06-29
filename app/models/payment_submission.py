"""
Payment Submission — Groups of payments that a Rep accumulates
and submits back to the Company. On approval, posted as a Journal Entry in ZAP.
"""
import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class SubmissionStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    posted = "posted"       # Journal Entry created in ZAP
    rejected = "rejected"


class PaymentSubmission(Base):
    __tablename__ = "payment_submissions"

    id = Column(Integer, primary_key=True)
    submission_ref = Column(String(50), unique=True, nullable=False, index=True)
    rep_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    total_amount = Column(Numeric(14, 2), nullable=False, default=0)
    status = Column(Enum(SubmissionStatus), nullable=False, default=SubmissionStatus.pending)
    # Denomination totals (aggregated from child payments)
    denom_2000_total = Column(Integer, nullable=False, default=0)
    denom_500_total = Column(Integer, nullable=False, default=0)
    denom_200_total = Column(Integer, nullable=False, default=0)
    denom_100_total = Column(Integer, nullable=False, default=0)
    denom_50_total = Column(Integer, nullable=False, default=0)
    denom_20_total = Column(Integer, nullable=False, default=0)
    denom_10_total = Column(Integer, nullable=False, default=0)
    # Online / bank references
    online_amount = Column(Numeric(14, 2), nullable=False, default=0)
    online_references = Column(Text, nullable=True)  # JSON array of refs
    # ZAP Journal Entry
    journal_entry_ref = Column(String(100), nullable=True)
    target_account = Column(String(255), nullable=True)
    # Approval
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    submitted_at = Column(DateTime, server_default=func.now())
    created_at = Column(DateTime, server_default=func.now())

    rep = relationship("User", foreign_keys=[rep_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
    payment_items = relationship("Payment", back_populates="submission", foreign_keys="Payment.submission_id")

    @property
    def payment_count(self) -> int:
        return len(self.payment_items)

    @property
    def cash_total(self) -> float:
        return float(self.total_amount) - float(self.online_amount)

    def status_badge_cls(self) -> str:
        return {
            SubmissionStatus.pending: "bg-amber-900/50 text-amber-300",
            SubmissionStatus.approved: "bg-blue-900/50 text-blue-300",
            SubmissionStatus.posted: "bg-emerald-900/50 text-emerald-300",
            SubmissionStatus.rejected: "bg-red-900/50 text-red-300",
        }.get(self.status, "bg-slate-700 text-slate-300")
