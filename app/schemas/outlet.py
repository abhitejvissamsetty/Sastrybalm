from typing import Optional
from pydantic import BaseModel
from app.models.outlet import OutletStatus


class OutletCreate(BaseModel):
    name: str
    code: Optional[str] = None
    owner_name: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    channel: Optional[str] = None
    beat_id: Optional[int] = None
    territory_id: Optional[int] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    erp_id: Optional[str] = None


class OutletResponse(BaseModel):
    id: int
    name: str
    code: Optional[str]
    owner_name: Optional[str]
    mobile: Optional[str]
    address: Optional[str]
    beat_id: Optional[int]
    territory_id: Optional[int]
    gps_lat: Optional[float]
    gps_lng: Optional[float]
    status: OutletStatus
    erp_id: Optional[str]

    model_config = {"from_attributes": True}
