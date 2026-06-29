from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.user import User
from app.schemas.auth import LoginRequest, TokenResponse, UserResponse
from app.services.auth import authenticate_user
from app.utils.security import create_access_token

router = APIRouter(prefix="/api/v1", tags=["mobile-api"])


@router.post("/auth/token", response_model=TokenResponse, summary="Mobile login — returns JWT")
async def api_login(payload: LoginRequest, db: Session = Depends(get_db)):
    print(f"[DEBUG AUTH] Login attempt for username/email: '{payload.username}' with password: '{payload.password}'")
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        print(f"[DEBUG AUTH] Authentication failed for user: '{payload.username}'")
        raise HTTPException(status_code=401, detail="Invalid credentials")

    from app.models.user import UserRole
    if user.role == UserRole.field_rep:
        from datetime import date
        from app.models.attendance import Attendance
        today = date.today()
        att = db.query(Attendance).filter(
            Attendance.user_id == user.id,
            Attendance.date == today
        ).first()
        if att and att.checkout_time is not None:
            raise HTTPException(
                status_code=400,
                detail="You have already logged out of this session, contact admin"
            )
    print(f"[DEBUG AUTH] Authentication successful for user: '{payload.username}' (ID: {user.id})")
    token = create_access_token({"sub": str(user.id), "role": user.role.value})
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        id=user.id,
        email=user.email,
        username=user.username,
        full_name=user.full_name,
        role=user.role,
        is_active=user.is_active,
        employee_id=user.employee_id,
        phone=user.phone,
        company_profile_id=user.company_profile_id,
    )


@router.get("/auth/me", response_model=UserResponse, summary="Get authenticated user profile")
async def api_me(current_user: User = Depends(require_api_auth)):
    return current_user
