from decimal import Decimal
from typing import Optional
from pydantic import BaseModel


class ProductCreate(BaseModel):
    name: str
    erp_id: Optional[str] = None
    sku: Optional[str] = None
    division: Optional[str] = None
    primary_category: Optional[str] = None
    secondary_category: Optional[str] = None
    mrp: Optional[Decimal] = None
    gst_rate: Optional[Decimal] = None
    must_sell: bool = False


class ProductResponse(BaseModel):
    id: int
    name: str
    erp_id: Optional[str]
    sku: Optional[str]
    division: Optional[str]
    primary_category: Optional[str]
    secondary_category: Optional[str]
    mrp: Optional[Decimal]
    gst_rate: Optional[Decimal]
    must_sell: bool
    is_active: bool

    model_config = {"from_attributes": True}
