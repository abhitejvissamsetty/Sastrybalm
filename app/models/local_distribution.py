from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.models.base import Base


class LocalChannelPartner(Base):
    __tablename__ = "local_channel_partners"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, index=True, nullable=False)
    name = Column(String(255), nullable=False)
    territory_name = Column(String(100), index=True, nullable=True)
    service_category = Column(String(100), index=True, nullable=True)
    phone = Column(String(20), nullable=True)
    email = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)


class PincodeTerritoryMapping(Base):
    __tablename__ = "pincode_territory_mappings"

    id = Column(Integer, primary_key=True, index=True)
    pincode = Column(String(10), unique=True, index=True, nullable=False)
    territory_name = Column(String(100), index=True, nullable=False)
    region_name = Column(String(100), nullable=True)
    state_name = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
