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
    in_manufacturing = "In Manufacturing"
    qc_pending = "QC Pending"
    completed = "Completed"
    cancelled = "Cancelled"


class QCStatus(str, enum.Enum):
    pending = "Pending"
    passed = "Passed"
    failed = "Failed"


class VendorQuotation(Base):
    __tablename__ = "vendor_quotations"

    id = Column(Integer, primary_key=True, index=True)
    material_request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    recce_id = Column(Integer, ForeignKey("recce_informations.id", ondelete="SET NULL"), nullable=True)
    quote_amount = Column(Numeric(10, 2), nullable=False)
    lead_time_days = Column(Integer, default=7)
    status = Column(SAEnum(QuotationStatus), default=QuotationStatus.pending, nullable=False)
    notes = Column(Text, nullable=True)
    counter_recce_notes = Column(Text, nullable=True)
    invoice_photo_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    material_request = relationship("MaterialRequest", backref="quotations")
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    recce = relationship("RecceInformation", foreign_keys=[recce_id])


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("vendor_quotations.id", ondelete="CASCADE"), nullable=True)
    material_request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="SET NULL"), nullable=True)
    wo_number = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SAEnum(WorkOrderStatus), default=WorkOrderStatus.issued, nullable=False)
    qc_status = Column(SAEnum(QCStatus), default=QCStatus.pending, nullable=False)
    manufactured_photo_url = Column(Text, nullable=True)
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
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    qc_verified_by = relationship("User", foreign_keys=[qc_verified_by_id])


class ProcurementItem(Base):
    __tablename__ = "procurement_items"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False)
    item_name = Column(String(255), nullable=False)
    batch_number = Column(String(100), unique=True, nullable=False, index=True)
    final_dimensions = Column(String(255), nullable=True)
    final_specifications = Column(Text, nullable=True)
    qc_notes = Column(Text, nullable=True)
    qc_manager_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="pending_installation", nullable=False)  # pending_installation, installed
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    work_order = relationship("WorkOrder", backref="procurement_items")
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    qc_manager = relationship("User", foreign_keys=[qc_manager_id])
