from __future__ import annotations
from typing import Optional
from pydantic import BaseModel

from app.models.user import UserRole


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: int
    id: int
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool = True
    employee_id: Optional[str] = None
    phone: Optional[str] = None
    company_profile_id: Optional[int] = None


class UserResponse(BaseModel):
    id: int
    email: str
    username: str
    full_name: str
    role: UserRole
    is_active: bool
    employee_id: Optional[str]
    phone: Optional[str]

    model_config = {"from_attributes": True}
