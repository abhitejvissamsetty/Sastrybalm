import enum

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base
from app.models.user import user_positions

# Junction table — Position ↔ Beat (many-to-many)
from sqlalchemy import Table
position_beats = Table(
    "position_beats",
    Base.metadata,
    Column("position_id", Integer, ForeignKey("positions.id"), primary_key=True),
    Column("beat_id", Integer, ForeignKey("beats.id"), primary_key=True),
)


class PositionLevel(str, enum.Enum):
    L1 = "L1"
    L2 = "L2"
    L3 = "L3"
    L4 = "L4"


class Position(Base):
    __tablename__ = "positions"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    level = Column(SAEnum(PositionLevel), nullable=False, default=PositionLevel.L1)
    reporting_to_id = Column(Integer, ForeignKey("positions.id"), nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    reporting_to = relationship("Position", remote_side=[id], backref="direct_reports")
    beats = relationship("Beat", secondary=position_beats, back_populates="positions")
    users = relationship("User", secondary=user_positions, back_populates="positions")

    @property
    def is_vacant(self) -> bool:
        """Position is vacant if no active users are attached."""
        return not any(u.is_active for u in self.users)

    @property
    def attached_users_display(self) -> str:
        active = [u.full_name for u in self.users if u.is_active]
        return ", ".join(active) if active else "Vacant"

    def vacancy_badge_cls(self) -> str:
        if self.is_vacant:
            return "bg-amber-900/50 text-amber-300"
        return "bg-emerald-900/50 text-emerald-300"
