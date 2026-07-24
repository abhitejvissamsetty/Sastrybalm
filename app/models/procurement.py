import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Numeric, ForeignKey, DateTime, Enum as SAEnum, Text
from sqlalchemy.orm import relationship
from app.models.base import Base


class QuotationStatus(str, enum.Enum):
    pending = "Pending"
    approved = "Approved"
    rejected = "Rejected"
    held = "Held"


class WorkOrderStatus(str, enum.Enum):
    issued = "Issued"
    concluded = "Concluded"
    cancelled = "Cancelled"


class QCStatus(str, enum.Enum):
    pending = "Pending"
    passed = "Passed"
    failed = "Failed"


class VendorQuotation(Base):
    __tablename__ = "vendor_quotations"

    id = Column(Integer, primary_key=True, index=True)
    material_request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    quote_amount = Column(Numeric(10, 2), nullable=False)
    lead_time_days = Column(Integer, default=7)
    status = Column(SAEnum(QuotationStatus), default=QuotationStatus.pending, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    material_request = relationship("MaterialRequest", backref="quotations")
    vendor = relationship("User", foreign_keys=[vendor_id])


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("vendor_quotations.id", ondelete="CASCADE"), nullable=False)
    wo_number = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SAEnum(WorkOrderStatus), default=WorkOrderStatus.issued, nullable=False)
    qc_status = Column(SAEnum(QCStatus), default=QCStatus.pending, nullable=False)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    quotation = relationship("VendorQuotation", backref="work_order")
