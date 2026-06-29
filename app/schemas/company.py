from typing import Optional
from pydantic import BaseModel
from app.models.company import PaymentMode


class CompanyProfileCreate(BaseModel):
    code: str
    name: str
    cmms_base_url: Optional[str] = None
    cmms_api_key: Optional[str] = None      # plain; encrypted before storage
    connect_base_url: Optional[str] = None
    connect_api_key: Optional[str] = None


class CompanyProfileResponse(BaseModel):
    id: int
    code: str
    name: str
    cmms_base_url: Optional[str]
    connect_base_url: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class SystemConfigResponse(BaseModel):
    payment_mode: PaymentMode
    denomination_mandatory: bool
    gps_threshold_metres: int
    sync_interval_seconds: int

    model_config = {"from_attributes": True}
