import enum
from typing import Optional

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, ForeignKey, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class GeoLevel(str, enum.Enum):
    zone = "zone"
    region = "region"
    territory = "territory"


class Geography(Base):
    __tablename__ = "geographies"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    code = Column(String(100), unique=True, nullable=False, index=True)
    level = Column(SAEnum(GeoLevel), nullable=False)
    parent_id = Column(Integer, ForeignKey("geographies.id"), nullable=True)
    erp_id = Column(String(100))
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())

    parent = relationship("Geography", remote_side=[id], backref="children")

    def level_badge(self) -> str:
        colours = {
            GeoLevel.zone: "bg-blue-50 text-blue-700 ring-blue-600/20",
            GeoLevel.region: "bg-indigo-50 text-indigo-700 ring-indigo-600/20",
            GeoLevel.territory: "bg-purple-50 text-purple-700 ring-purple-600/20",
        }
        return colours.get(self.level, "bg-gray-100 text-gray-600")

    def breadcrumb(self) -> str:
        parts: list[str] = [self.name]
        p = self.parent
        while p:
            parts.insert(0, p.name)
            p = p.parent
        return " › ".join(parts)
