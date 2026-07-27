"""
Asset Capitalization — Records of marketing materials being hosted at outlets.
No approval needed — goes direct to CMMS queue.
Rep or Vendor Technician picks the item from CMMS-assigned warehouse.
"""
import enum

from sqlalchemy import Column, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ACStatus(str, enum.Enum):
    pending = "pending"
    deployed = "deployed"
    failed = "failed"


class ACSyncStatus(str, enum.Enum):
    not_applicable = "not_applicable"
    pending = "pending"
    synced = "synced"
    failed = "failed"


class DeployedByType(str, enum.Enum):
    rep = "rep"
    vendor_technician = "vendor_technician"


class AssetCapitalization(Base):
    __tablename__ = "asset_capitalizations"

    id = Column(Integer, primary_key=True)
    ac_number = Column(String(30), unique=True, nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="RESTRICT"), nullable=False)
    company_profile_id = Column(Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True)
    # Item details (from CMMS)
    item_name = Column(String(255), nullable=False)
    item_code = Column(String(100), nullable=True)
    quantity = Column(Integer, nullable=False, default=1)
    warehouse_name = Column(String(255), nullable=True)
    # Deployment
    deployed_by = Column(Enum(DeployedByType), nullable=False, default=DeployedByType.rep)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="SET NULL"), nullable=True)
    vendor_employee_id = Column(Integer, ForeignKey("vendor_employees.id", ondelete="SET NULL"), nullable=True)
    # Status & sync
    status = Column(Enum(ACStatus), nullable=False, default=ACStatus.pending)
    sync_status = Column(Enum(ACSyncStatus), nullable=False, default=ACSyncStatus.not_applicable)
    cmms_ref = Column(String(100), nullable=True)
    sync_error = Column(Text, nullable=True)
    # Procurement link & QC validation
    procurement_item_id = Column(Integer, ForeignKey("procurement_items.id", ondelete="SET NULL"), nullable=True)
    qc_verified = Column(Enum(ACStatus), nullable=False, default=ACStatus.pending)
    qc_notes = Column(Text, nullable=True)

    notes = Column(Text, nullable=True)
    image_url = Column(Text, nullable=True)
    deployed_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    user = relationship("User", foreign_keys=[user_id])
    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    company_profile = relationship("CompanyProfile", foreign_keys=[company_profile_id])
    vendor = relationship("Vendor", foreign_keys=[vendor_id])
    vendor_employee = relationship("VendorEmployee", foreign_keys=[vendor_employee_id])
    procurement_item = relationship("ProcurementItem", foreign_keys=[procurement_item_id])

    def status_badge_cls(self) -> str:
        return {
            ACStatus.pending: "bg-amber-900/50 text-amber-300",
            ACStatus.deployed: "bg-emerald-900/50 text-emerald-300",
            ACStatus.failed: "bg-red-900/50 text-red-300",
        }.get(self.status, "bg-slate-700 text-slate-300")

    def sync_badge_cls(self) -> str:
        return {
            ACSyncStatus.not_applicable: "bg-slate-700 text-slate-400",
            ACSyncStatus.pending: "bg-amber-900/50 text-amber-300",
            ACSyncStatus.synced: "bg-emerald-900/50 text-emerald-300",
            ACSyncStatus.failed: "bg-red-900/50 text-red-300",
        }.get(self.sync_status, "bg-slate-700 text-slate-300")


class AssetMaintenanceLog(Base):
    __tablename__ = "asset_maintenance_logs"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("asset_capitalizations.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    notes = Column(Text, nullable=False)
    photo_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    asset = relationship("AssetCapitalization", backref="maintenance_logs")
    created_by = relationship("User", foreign_keys=[created_by_id])

