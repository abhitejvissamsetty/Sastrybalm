from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class RecceInformation(Base):
    __tablename__ = "recce_informations"

    id = Column(Integer, primary_key=True, index=True)
    material_request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    dimensions = Column(String(255), nullable=True)
    dimension_length = Column(Numeric(10, 2), nullable=True)
    dimension_width = Column(Numeric(10, 2), nullable=True)
    dimension_height = Column(Numeric(10, 2), nullable=True)
    dimension_depth = Column(Numeric(10, 2), nullable=True)
    dimension_unit = Column(String(20), nullable=True, default="cm")
    status = Column(String(30), nullable=False, default="Submitted")
    description = Column(Text, nullable=True)
    location_notes = Column(Text, nullable=True)
    approved_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    approved_at = Column(DateTime, nullable=True)
    rejection_reason = Column(Text, nullable=True)
    version = Column(Integer, nullable=False, default=1)
    material_specifications = Column(Text, nullable=True)
    client_notes = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    material_request = relationship("MaterialRequest", backref="recces")
    vendor = relationship("Vendor", backref="recces")
    created_by = relationship("User", foreign_keys=[created_by_id])
    approved_by = relationship("User", foreign_keys=[approved_by_id])
