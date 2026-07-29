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
    assigned = "Assigned"
    acknowledged = "Acknowledged"
    in_manufacturing = "In Manufacturing"
    qc_pending = "QC Pending"
    completed = "Completed"
    paid = "Paid"
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
    base_amount = Column(Numeric(12, 2), nullable=True)
    gst_percent = Column(Numeric(5, 2), nullable=True)
    gst_amount = Column(Numeric(12, 2), nullable=True)
    total_amount = Column(Numeric(12, 2), nullable=True)
    lead_time_days = Column(Integer, default=7)
    status = Column(SAEnum(QuotationStatus), default=QuotationStatus.pending, nullable=False)
    notes = Column(Text, nullable=True)
    counter_recce_notes = Column(Text, nullable=True)
    invoice_photo_url = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    submitted_at = Column(DateTime, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)

    is_archived = Column(Boolean, default=False, nullable=False, index=True)
    archived_at = Column(DateTime, nullable=True)

    material_request = relationship("MaterialRequest", backref="quotations")
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    recce = relationship("RecceInformation", foreign_keys=[recce_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])


class WorkOrder(Base):
    __tablename__ = "work_orders"

    id = Column(Integer, primary_key=True, index=True)
    quotation_id = Column(Integer, ForeignKey("vendor_quotations.id", ondelete="CASCADE"), nullable=True)
    material_request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="SET NULL"), nullable=True)
    wo_number = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(SAEnum(WorkOrderStatus), default=WorkOrderStatus.issued, nullable=False)
    progress_percent = Column(Integer, default=0, nullable=False)
    acknowledged_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    acknowledged_at = Column(DateTime, nullable=True)
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
    acknowledged_by = relationship("User", foreign_keys=[acknowledged_by_id])


class ProcurementItem(Base):
    __tablename__ = "procurement_items"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False)
    product_id = Column(Integer, ForeignKey("products.id", ondelete="RESTRICT"), nullable=True, index=True)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id", ondelete="RESTRICT"), nullable=True, index=True)
    qc_report_id = Column(Integer, ForeignKey("qc_reports.id", ondelete="SET NULL"), nullable=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False)
    item_name = Column(String(255), nullable=False)
    batch_number = Column(String(100), unique=True, nullable=False, index=True)
    final_dimensions = Column(String(255), nullable=True)
    final_specifications = Column(Text, nullable=True)
    qc_notes = Column(Text, nullable=True)
    qc_manager_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    status = Column(String(50), default="Ready", nullable=False)
    invalidated_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    work_order = relationship("WorkOrder", backref="procurement_items")
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    qc_manager = relationship("User", foreign_keys=[qc_manager_id])
    product = relationship("Product", foreign_keys=[product_id])
    warehouse = relationship("Warehouse", foreign_keys=[warehouse_id])
    qc_report = relationship("QCReport", foreign_keys=[qc_report_id])


class WorkOrderProgressLog(Base):
    __tablename__ = "work_order_progress_logs"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    progress_percent = Column(Integer, nullable=False)
    remarks = Column(Text, nullable=True)
    reported_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    work_order = relationship("WorkOrder", backref="progress_logs")
    reported_by = relationship("User", foreign_keys=[reported_by_id])


class QCReport(Base):
    __tablename__ = "qc_reports"

    id = Column(Integer, primary_key=True, index=True)
    work_order_id = Column(Integer, ForeignKey("work_orders.id", ondelete="CASCADE"), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="Passed")
    remark = Column(Text, nullable=False)
    maintenance_schedule = Column(String(255), nullable=True)
    reported_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    reported_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    is_valid = Column(Boolean, default=True, nullable=False)

    work_order = relationship("WorkOrder", backref="qc_reports")
    reported_by = relationship("User", foreign_keys=[reported_by_id])


class ProcurementAttachment(Base):
    __tablename__ = "procurement_attachments"

    id = Column(Integer, primary_key=True, index=True)
    entity_type = Column(String(40), nullable=False, index=True)
    entity_id = Column(Integer, nullable=False, index=True)
    attachment_type = Column(String(50), nullable=False)
    file_url = Column(Text, nullable=False)
    uploaded_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    uploaded_by = relationship("User", foreign_keys=[uploaded_by_id])
