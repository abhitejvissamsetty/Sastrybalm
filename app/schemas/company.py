from typing import Optional
from pydantic import BaseModel
from app.models.company import PaymentMode


class CompanyProfileCreate(BaseModel):
    code: str
    name: str


class CompanyProfileResponse(BaseModel):
    id: int
    code: str
    name: str
    is_active: bool

    model_config = {"from_attributes": True}


class SystemConfigResponse(BaseModel):
    payment_mode: PaymentMode
    denomination_mandatory: bool
    gps_threshold_metres: int
    sync_interval_seconds: int

    model_config = {"from_attributes": True}
