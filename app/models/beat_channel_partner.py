from datetime import datetime
from sqlalchemy import Column, Integer, ForeignKey, DateTime
from app.models.base import Base


class BeatChannelPartner(Base):
    __tablename__ = "beat_channel_partners"

    id = Column(Integer, primary_key=True, index=True)
    beat_id = Column(Integer, ForeignKey("beats.id", ondelete="CASCADE"), nullable=False, index=True)
    channel_partner_id = Column(Integer, ForeignKey("local_channel_partners.id", ondelete="CASCADE"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
