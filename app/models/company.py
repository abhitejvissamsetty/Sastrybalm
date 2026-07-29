import enum
import json

from sqlalchemy import Boolean, Column, DateTime, Enum as SAEnum, Integer, String, Text
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.models.base import Base


class PaymentMode(str, enum.Enum):
    cash_only = "cash_only"
    online_only = "online_only"
    cash_and_online = "cash_and_online"


class CompanyProfile(Base):
    __tablename__ = "company_profiles"

    id = Column(Integer, primary_key=True, index=True)
    code = Column(String(100), unique=True, nullable=False, index=True)
    name = Column(String(255), nullable=False)

    # Optional internal labels.
    tags = Column(Text, default="[]")

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    # Relationships
    product_mappings = relationship("ProductAliasMap", back_populates="company_profile", cascade="all, delete-orphan")
    account_mappings = relationship("AccountAliasMap", back_populates="company_profile", cascade="all, delete-orphan")

    def get_tags(self) -> list[str]:
        try:
            return json.loads(self.tags or "[]")
        except (json.JSONDecodeError, TypeError):
            return []

    def set_tags(self, tag_list: list[str]):
        self.tags = json.dumps(tag_list)

    def add_tag(self, tag: str):
        tags = self.get_tags()
        if tag not in tags:
            tags.append(tag)
            self.set_tags(tags)

    def remove_tag(self, tag: str):
        tags = self.get_tags()
        if tag in tags:
            tags.remove(tag)
            self.set_tags(tags)

    def has_tag(self, tag: str) -> bool:
        return tag in self.get_tags()

    def tag_badges(self) -> list[dict]:
        badge_map = {}
        return [
            {"name": t, "cls": badge_map.get(t, "bg-slate-700 text-slate-300")}
            for t in self.get_tags()
        ]


class SystemConfiguration(Base):
    """Singleton settings record — always id=1."""
    __tablename__ = "system_configuration"

    id = Column(Integer, primary_key=True, default=1)
    # Mobile frontend behaviour
    gps_threshold_metres = Column(Integer, default=100, nullable=False)
    sync_interval_seconds = Column(Integer, default=300, nullable=False)
    # Auto-flagging thresholds
    flag_gps_distance_metres = Column(Integer, default=100, nullable=False)
    flag_min_visit_seconds = Column(Integer, default=120, nullable=False)  # 2 minutes
    
    # Global payment settings
    payment_mode = Column(SAEnum(PaymentMode), nullable=True, default=PaymentMode.cash_only)
    denomination_mandatory = Column(Boolean, default=False, nullable=False)

    # SMTP credentials are encrypted before database persistence.
    smtp_host = Column(String(255), nullable=True)
    smtp_port = Column(Integer, default=587, nullable=False)
    smtp_user = Column(String(255), nullable=True)
    smtp_password = Column(Text, nullable=True)
    smtp_from = Column(String(255), nullable=True)
    smtp_use_tls = Column(Boolean, default=True, nullable=False)

    # Order Auto-Approval Cutoff Setting
    auto_approval_cutoff_hours = Column(Integer, default=24, nullable=False)

    # Backblaze B2 / AWS S3 Storage — 1. Images Bucket (Photos, Outlets, QC, Avatars)
    s3_is_enabled = Column(Boolean, default=False, nullable=False)
    s3_endpoint_url = Column(String(255), nullable=True)
    s3_bucket_name = Column(String(255), nullable=True)
    s3_access_key_id = Column(String(255), nullable=True)
    s3_secret_access_key = Column(Text, nullable=True)
    s3_region_name = Column(String(100), default="us-west-004", nullable=True)
    s3_public_url_prefix = Column(String(255), nullable=True)

    # Backblaze B2 / AWS S3 Storage — 2. Files & Documents Bucket (Database Backups, PDFs, Reports)
    s3_files_is_enabled = Column(Boolean, default=False, nullable=False)
    s3_files_endpoint_url = Column(String(255), nullable=True)
    s3_files_bucket_name = Column(String(255), nullable=True)
    s3_files_access_key_id = Column(String(255), nullable=True)
    s3_files_secret_access_key = Column(Text, nullable=True)
    s3_files_region_name = Column(String(100), default="us-west-004", nullable=True)
    s3_files_public_url_prefix = Column(String(255), nullable=True)

    # Parquet Archival Retention Setting
    archival_retention_days = Column(Integer, default=90, nullable=False)

    # WhatsApp Business API Configuration
    whatsapp_api_key = Column(Text, nullable=True)
    whatsapp_phone_number_id = Column(String(255), nullable=True)
    whatsapp_business_account_id = Column(String(255), nullable=True)
    whatsapp_is_enabled = Column(Boolean, default=False, nullable=False)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
