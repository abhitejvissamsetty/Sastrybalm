"""
Vendor & Vendor Employee models for CMMS procurement workflow.
Vendors are mobile-only with separate login. Admin can view procurement timeline.
"""
import enum

from sqlalchemy import Boolean, Column, DateTime, Enum, ForeignKey, Integer, String, Table, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class VendorStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


# Many-to-many: Vendor ↔ Product (Product Scope)
vendor_products = Table(
    "vendor_products",
    Base.metadata,
    Column("vendor_id", Integer, ForeignKey("vendors.id", ondelete="CASCADE"), primary_key=True),
    Column("product_id", Integer, ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
)


class Vendor(Base):
    __tablename__ = "vendors"

    id = Column(Integer, primary_key=True)
    name = Column(String(255), nullable=False)
    contact_person = Column(String(255), nullable=True)
    mobile = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), unique=True, nullable=True)
    category = Column(String(100), nullable=True)
    status = Column(Enum(VendorStatus), nullable=False, default=VendorStatus.active)
    cmms_supplier_ref = Column(String(100), nullable=True)
    # Scope Fields
    geography_id = Column(Integer, ForeignKey("geographies.id", ondelete="SET NULL"), nullable=True)
    # Auth for vendor mobile login
    hashed_password = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    geography = relationship("Geography", foreign_keys=[geography_id])
    supplied_products = relationship("Product", secondary=vendor_products)
    employees = relationship("VendorEmployee", back_populates="vendor", cascade="all, delete-orphan")

    def status_badge_cls(self) -> str:
        return {
            VendorStatus.active: "bg-emerald-900/50 text-emerald-300",
            VendorStatus.inactive: "bg-gray-700 text-gray-400",
        }.get(self.status, "bg-slate-700 text-slate-300")


class VendorEmployee(Base):
    __tablename__ = "vendor_employees"

    id = Column(Integer, primary_key=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(255), nullable=False)
    mobile = Column(String(20), unique=True, nullable=True)
    email = Column(String(255), nullable=True)
    cmms_ref = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    # Auth for technician mobile login
    hashed_password = Column(String(255), nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    vendor = relationship("Vendor", back_populates="employees")
