from typing import Optional
from pydantic import BaseModel, EmailStr
from app.models.user import UserRole, ModuleName


class UserCreate(BaseModel):
    email: str
    username: str
    full_name: str
    password: str
    role: UserRole
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    position_id: Optional[int] = None
    zone_id: Optional[int] = None
    company_profile_id: Optional[int] = None


class UserUpdate(BaseModel):
    email: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[UserRole] = None
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    position_id: Optional[int] = None
    zone_id: Optional[int] = None
    company_profile_id: Optional[int] = None
    is_active: Optional[bool] = None
    new_password: Optional[str] = None


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    employee_id: Optional[str]
    phone: Optional[str]
    position_id: Optional[int]
    zone_id: Optional[int]
    company_profile_id: Optional[int]
    imei: Optional[str]
    active_modules: list[str] = []

    model_config = {"from_attributes": True}
