from typing import Optional
from pydantic import BaseModel
from app.models.geography import GeoLevel


class GeographyCreate(BaseModel):
    name: str
    code: str
    level: GeoLevel
    parent_id: Optional[int] = None
    erp_id: Optional[str] = None


class GeographyResponse(BaseModel):
    id: int
    name: str
    code: str
    level: GeoLevel
    parent_id: Optional[int]
    erp_id: Optional[str]
    is_active: bool

    model_config = {"from_attributes": True}


class GeographyTreeNode(BaseModel):
    id: int
    name: str
    code: str
    level: str
    children: list["GeographyTreeNode"] = []

    model_config = {"from_attributes": True}


GeographyTreeNode.model_rebuild()
