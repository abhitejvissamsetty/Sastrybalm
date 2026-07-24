import enum
from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class ProductCategory(str, enum.Enum):
    sales = "Sales"
    marketing_procurement = "Marketing - Procurement"
    marketing_stock = "Marketing - Stock"


class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    erp_id = Column(String(100), unique=True, nullable=True, index=True)
    sku = Column(String(100), unique=True, nullable=True, index=True)
    name = Column(String(255), nullable=False)
    division = Column(String(100), nullable=True)
    category_type = Column(
        SAEnum(ProductCategory, values_callable=lambda x: [e.value for e in x]),
        default=ProductCategory.sales,
        nullable=False
    )
    primary_category = Column(String(100), nullable=True)
    secondary_category = Column(String(100), nullable=True)
    mrp = Column(Numeric(10, 2), default=0)
    unit_cost = Column(Numeric(10, 2), default=0)
    stock_qty = Column(Integer, default=0, nullable=False)
    reorder_level = Column(Integer, default=10, nullable=False)
    warehouse_id = Column(Integer, ForeignKey("warehouses.id", ondelete="SET NULL"), nullable=True, index=True)
    warehouse_location = Column(String(100), nullable=True)
    gst_rate = Column(Numeric(5, 2), default=0)   # e.g. 18.00 means 18 %
    must_sell = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    warehouse = relationship("Warehouse", back_populates="products")

    @property
    def display_price(self) -> str:
        return f"₹{self.mrp:.2f}" if self.mrp else "—"
