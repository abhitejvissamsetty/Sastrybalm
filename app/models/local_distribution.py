import json
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.models.base import Base


class LocalChannelPartner(Base):
    __tablename__ = "local_channel_partners"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=True)
    name = Column(String(255), nullable=False)
    partner_type = Column(String(100), nullable=True, default="Distributor")
    beat_type = Column(String(50), nullable=True, default="GT")
    sales_channels = Column(Text, nullable=True)  # Stores JSON list of selected sales channel codes e.g. ["GT", "MT"]
    geography_id = Column(Integer, ForeignKey("geographies.id", ondelete="SET NULL"), nullable=True, index=True)
    territory_name = Column(String(100), index=True, nullable=True)
    service_category = Column(String(100), index=True, nullable=True)
    contact_person = Column(String(255), nullable=True)
    mobile = Column(String(20), nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    address = Column(Text, nullable=True)
    erp_id = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    geography = relationship("Geography", foreign_keys=[geography_id])

    @property
    def sales_channels_list(self) -> list:
        if not self.sales_channels:
            return [self.beat_type] if self.beat_type else []
        try:
            return json.loads(self.sales_channels)
        except Exception:
            return [s.strip() for s in self.sales_channels.split(",") if s.strip()]


class PincodeTerritoryMapping(Base):
    __tablename__ = "pincode_territory_mappings"

    id = Column(Integer, primary_key=True, index=True)
    pincode = Column(String(10), unique=True, index=True, nullable=False)
    territory_name = Column(String(100), index=True, nullable=False)
    region_name = Column(String(100), nullable=True)
    state_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
