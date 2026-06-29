from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    erp_id = Column(String(100), unique=True, nullable=True, index=True)
    sku = Column(String(100), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    division = Column(String(100))
    primary_category = Column(String(100))
    secondary_category = Column(String(100))
    mrp = Column(Numeric(10, 2), default=0)
    gst_rate = Column(Numeric(5, 2), default=0)   # e.g. 18.00 means 18 %
    must_sell = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    # Company profile scoping — nullable for shared products
    company_profile_id = Column(
        Integer, ForeignKey("company_profiles.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    company_profile = relationship("CompanyProfile", back_populates="products")

    @property
    def display_price(self) -> str:
        return f"₹{self.mrp:.2f}" if self.mrp else "—"
