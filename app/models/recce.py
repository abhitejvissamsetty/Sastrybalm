from datetime import datetime
from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import relationship
from app.models.base import Base

class RecceInformation(Base):
    __tablename__ = "recce_informations"

    id = Column(Integer, primary_key=True, index=True)
    material_request_id = Column(Integer, ForeignKey("material_requests.id", ondelete="CASCADE"), nullable=False, index=True)
    vendor_id = Column(Integer, ForeignKey("vendors.id", ondelete="CASCADE"), nullable=False, index=True)
    created_by_id = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    
    dimensions = Column(String(255), nullable=True)
    material_specifications = Column(Text, nullable=True)
    client_notes = Column(Text, nullable=True)
    photo_url = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    material_request = relationship("MaterialRequest", backref="recces")
    vendor = relationship("Vendor", backref="recces")
    created_by = relationship("User", foreign_keys=[created_by_id])
