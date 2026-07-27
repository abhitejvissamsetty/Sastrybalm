from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class Warehouse(Base):
    __tablename__ = "warehouses"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    pincode = Column(String(10), nullable=True)
    address = Column(String(500), nullable=True)
    contact_person = Column(String(255), nullable=True)
    mobile = Column(String(20), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    # Region assignment (Geography)
    geography_id = Column(Integer, ForeignKey("geographies.id", ondelete="SET NULL"), nullable=True)

    geography = relationship("Geography", back_populates="warehouses", foreign_keys=[geography_id])
    products = relationship("Product", back_populates="warehouse")
