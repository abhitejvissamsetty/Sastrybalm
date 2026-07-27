"""
Outlet Version Model — Audit log and Git-tree style version snapshots for Outlets.
Allows Admins to revert Outlet modifications to prior states.
"""
from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class OutletVersion(Base):
    __tablename__ = "outlet_versions"

    id = Column(Integer, primary_key=True, index=True)
    outlet_id = Column(Integer, ForeignKey("outlets.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)

    # Snapshot of outlet properties
    name = Column(String(255), nullable=False)
    code = Column(String(100), nullable=True)
    owner_name = Column(String(255), nullable=True)
    mobile = Column(String(20), nullable=True)
    address = Column(Text, nullable=True)
    pincode = Column(String(6), nullable=True)
    gstin = Column(String(15), nullable=True)
    channel = Column(String(50), nullable=True)
    shop_type = Column(String(50), nullable=True)
    beat_id = Column(Integer, nullable=True)
    territory_id = Column(Integer, nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    status = Column(String(50), nullable=True)

    # Audit tracking
    changed_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    change_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())

    outlet = relationship("Outlet", foreign_keys=[outlet_id])
    changed_by = relationship("User", foreign_keys=[changed_by_id])
