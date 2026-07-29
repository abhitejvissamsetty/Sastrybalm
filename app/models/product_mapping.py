"""Product and account aliases scoped to each company profile."""
from sqlalchemy import Column, ForeignKey, Integer, String, Numeric
from sqlalchemy.orm import relationship

from app.models.base import Base


class ProductAliasMap(Base):
    __tablename__ = "product_alias_maps"

    id = Column(Integer, primary_key=True)
    company_profile_id = Column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    product_id = Column(
        Integer, ForeignKey("products.id", ondelete="CASCADE"), nullable=False, index=True
    )
    conversion_factor = Column(Numeric(10, 5), default=1.0, nullable=False)

    company_profile = relationship("CompanyProfile", back_populates="product_mappings")
    product = relationship("Product")


class AccountAliasMap(Base):
    __tablename__ = "account_alias_maps"

    id = Column(Integer, primary_key=True)
    company_profile_id = Column(
        Integer, ForeignKey("company_profiles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    account_name = Column(String(255), nullable=False)
    account_type = Column(String(50), nullable=True)  # receivable, payable, bank, cash

    company_profile = relationship("CompanyProfile", back_populates="account_mappings")
