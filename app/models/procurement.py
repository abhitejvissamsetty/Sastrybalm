import enum
from datetime import datetime
from sqlalchemy import Boolean, Column, Integer, String, Numeric, ForeignKey, DateTime, Enum as SAEnum, Text
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
    invoice_photo_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    material_request = relationship("MaterialRequest", backref="quotations")
    vendor = relationship("User", foreign_keys=[vendor_id])


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("vendor_quotations.id", ondelete="CASCADE"), nullable=True)
    material_request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    wo_number = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SAEnum(WorkOrderStatus), default=WorkOrderStatus.issued, nullable=False)
    qc_status = Column(SAEnum(QCStatus), default=QCStatus.pending, nullable=False)
    qc_photo_url = Column(Text, nullable=True)
    qc_notes = Column(Text, nullable=True)
    qc_verified_at = Column(DateTime, nullable=True)
    qc_verified_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    quotation = relationship("VendorQuotation", backref="work_order")
    material_request = relationship("MaterialRequest", backref="work_orders")
    vendor = relationship("User", foreign_keys=[vendor_id])
    qc_verified_by = relationship("User", foreign_keys=[qc_verified_by_id])
