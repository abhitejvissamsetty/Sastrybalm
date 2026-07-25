import enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.position import position_beats


class BeatType(str, enum.Enum):
    GT = "GT"   # General Trade
    MT = "MT"   # Modern Trade
    pharmacy = "pharmacy"
    horeca = "horeca"
    institutional = "institutional"
    other = "other"


class BeatGrade(str, enum.Enum):
    rural = "Rural"
    urban = "Urban"
    semi_urban = "Semi Urban"
    metro = "Metro"
    non_metro = "Non-Metro"


def parse_beat_type(val: str) -> BeatType:
    if not val:
        return BeatType.GT
    val_clean = str(val).strip()
    val_upper = val_clean.upper()
    val_lower = val_clean.lower()
    for bt in BeatType:
        if bt.value == val_clean or bt.value.upper() == val_upper or bt.value.lower() == val_lower or bt.name.upper() == val_upper:
            return bt
    return BeatType.GT


from typing import Optional


def parse_beat_grade(val: Optional[str]) -> Optional[BeatGrade]:
    if not val:
        return None
    val_clean = str(val).strip()
    val_lower = val_clean.lower()
    for bg in BeatGrade:
        if bg.value.lower() == val_lower or bg.name.lower() == val_lower:
            return bg
    return None


class Beat(Base):
    __tablename__ = "beats"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    description = Column(String(500), nullable=True)
    pincodes = Column(String(500), nullable=True)
    beat_type = Column(SAEnum(BeatType), nullable=False, default=BeatType.GT)
    beat_grade = Column(SAEnum(BeatGrade), nullable=True)
    territory_id = Column(Integer, ForeignKey("geographies.id"), nullable=True)
    erp_id = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    territory = relationship("Geography", foreign_keys=[territory_id])
    outlets = relationship("Outlet", back_populates="beat")
    positions = relationship("Position", secondary=position_beats, back_populates="beats")

    @property
    def active_outlet_count(self) -> int:
        return sum(1 for o in self.outlets if o.status.value == "active")

    @property
    def has_active_dependencies(self) -> bool:
        """Check if beat has active outlets or positions linked."""
        has_outlets = any(o.status.value == "active" for o in self.outlets)
        has_positions = any(p.is_active for p in self.positions)
        return has_outlets or has_positions
