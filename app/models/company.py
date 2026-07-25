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

    # ZAP Integration
    zap_base_url = Column(String(500))
    zap_api_key_encrypted = Column(Text)  # format: api_key:api_secret (encrypted)
    zap_backend_company = Column(String(255))

    # CMMS Integration
    cmms_base_url = Column(String(500))
    cmms_api_key_encrypted = Column(Text)
    cmms_backend_company = Column(String(255))

    # CONNECT Integration
    connect_base_url = Column(String(500))
    connect_api_key_encrypted = Column(Text)
    connect_backend_company = Column(String(255))

    # Tags: JSON array e.g. ["ZAP-READY","CMMS-READY","CONNECT-READY"]
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

    @property
    def is_zap_ready(self) -> bool:
        return self.has_tag("ZAP-READY")

    @property
    def is_cmms_ready(self) -> bool:
        return self.has_tag("CMMS-READY")

    @property
    def is_connect_ready(self) -> bool:
        return self.has_tag("CONNECT-READY")

    def tag_badges(self) -> list[dict]:
        badge_map = {
            "ZAP-READY": "bg-emerald-900/50 text-emerald-300",
            "CMMS-READY": "bg-blue-900/50 text-blue-300",
            "CONNECT-READY": "bg-purple-900/50 text-purple-300",
            "ZAP-ERROR": "bg-red-900/50 text-red-300",
            "CMMS-ERROR": "bg-red-900/50 text-red-300",
            "CONNECT-ERROR": "bg-red-900/50 text-red-300",
        }
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

    # Order Auto-Approval Cutoff Setting
    auto_approval_cutoff_hours = Column(Integer, default=24, nullable=False)

    # Backblaze B2 S3 Object Storage Configuration
    s3_endpoint_url = Column(String(255), nullable=True)
    s3_bucket_name = Column(String(255), nullable=True)
    s3_access_key_id = Column(String(255), nullable=True)
    s3_secret_access_key = Column(Text, nullable=True)
    s3_region_name = Column(String(100), default="us-west-004", nullable=True)
    s3_is_enabled = Column(Boolean, default=False, nullable=False)
    s3_public_url_prefix = Column(String(255), nullable=True)

    # WhatsApp Business API Configuration
    whatsapp_api_key = Column(Text, nullable=True)
    whatsapp_phone_number_id = Column(String(255), nullable=True)
    whatsapp_business_account_id = Column(String(255), nullable=True)
    whatsapp_is_enabled = Column(Boolean, default=False, nullable=False)

    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
