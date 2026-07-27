import enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class OutletStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"


class ShopType(str, enum.Enum):
    kirana = "kirana"
    medical = "medical"
    general = "general"
    supermarket = "supermarket"
    hardware = "hardware"
    other = "other"


class ChannelType(str, enum.Enum):
    GT = "GT"   # General Trade
    MT = "MT"   # Modern Trade
    pharmacy = "pharmacy"
    horeca = "horeca"
    institutional = "institutional"
    other = "other"


class Outlet(Base):
    __tablename__ = "outlets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), unique=True, nullable=True, index=True)
    owner_name = Column(String(255))
    mobile = Column(String(20), unique=True, nullable=True, index=True)
    address = Column(Text)
    pincode = Column(String(6), nullable=True)
    gstin = Column(String(15), nullable=True)
    channel = Column(SAEnum(ChannelType), nullable=True)
    shop_type = Column(SAEnum(ShopType), nullable=True)
    external_id = Column(String(100), nullable=True, index=True)  # Fieldassist mapping
    beat_id = Column(Integer, ForeignKey("beats.id"), nullable=True)
    territory_id = Column(Integer, ForeignKey("geographies.id"), nullable=True)
    gps_lat = Column(Float)
    gps_lng = Column(Float)
    photo_url = Column(Text, nullable=True)
    erp_id = Column(String(100))
    status = Column(SAEnum(OutletStatus), default=OutletStatus.active, nullable=False)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    beat = relationship("Beat", back_populates="outlets")
    territory = relationship("Geography", foreign_keys=[territory_id])

    def status_badge_cls(self) -> str:
        mapping = {
            OutletStatus.active: "bg-emerald-900/50 text-emerald-300 ring-emerald-600/20",
            OutletStatus.inactive: "bg-gray-700 text-gray-400 ring-gray-500/20",
        }
        return mapping.get(self.status, "bg-gray-700 text-gray-400")

    def channel_display(self) -> str:
        if self.channel:
            return self.channel.value
        return "—"

    def shop_type_display(self) -> str:
        if self.shop_type:
            return self.shop_type.value.replace("_", " ").title()
        return "—"
