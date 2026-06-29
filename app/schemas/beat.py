from typing import Optional
from pydantic import BaseModel
from app.models.beat import BeatType


class BeatCreate(BaseModel):
    name: str
    code: str
    beat_type: BeatType
    territory_id: Optional[int] = None
    erp_id: Optional[str] = None


class BeatResponse(BaseModel):
    id: int
    name: str
    code: str
    beat_type: BeatType
    territory_id: Optional[int]
    erp_id: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}
