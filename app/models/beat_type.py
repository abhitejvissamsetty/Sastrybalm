from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from app.models.base import Base


class BeatTypeMaster(Base):
    __tablename__ = "beat_types_master"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(50), unique=True, nullable=False, index=True)
    name = Column(String(100), nullable=False)
    description = Column(String(255), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
