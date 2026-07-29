from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_api_auth
from app.models.user import User, UserRole
from app.schemas.auth import (
    LoginRequest,
    RequestOtpSchema,
    TokenResponse,
    UserResponse,
    VerifyOtpSchema,
)
from app.services.auth import (
    authenticate_user,
    generate_and_send_user_otp,
    verify_user_otp,
)
from app.utils.security import create_access_token

router = APIRouter(prefix="/api/v1", tags=["mobile-api"])


@router.post("/auth/token", response_model=TokenResponse, summary="Mobile login — returns JWT")
async def api_login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate_user(db, payload.username, payload.password)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials.")

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

    token = create_access_token({
        "sub": str(user.id), "role": user.role.value, "ver": user.token_version
    })
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
        can_access_restricted_modules=user.can_access_restricted_modules,
    )


@router.post("/auth/request-otp", summary="Request an email OTP")
async def api_request_otp(payload: RequestOtpSchema, db: Session = Depends(get_db)):
    result = generate_and_send_user_otp(db, payload.email)
    if not result["success"]:
        raise HTTPException(status_code=400, detail=result["error"])
    return {"message": result["message"], "email": result["email"]}


@router.post("/auth/verify-otp", response_model=TokenResponse)
async def api_verify_otp(payload: VerifyOtpSchema, db: Session = Depends(get_db)):
    user = verify_user_otp(db, payload.email, payload.otp_code)
    if not user:
        raise HTTPException(status_code=400, detail="Invalid or expired OTP code")
    if user.role == UserRole.field_rep:
        from datetime import date
        from app.models.attendance import Attendance

        attendance = db.query(Attendance).filter(
            Attendance.user_id == user.id,
            Attendance.date == date.today(),
        ).first()
        if attendance and attendance.checkout_time is not None:
            raise HTTPException(
                status_code=400,
                detail="You have already logged out of this session, contact admin",
            )
    token = create_access_token({
        "sub": str(user.id), "role": user.role.value, "ver": user.token_version
    })
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
        can_access_restricted_modules=user.can_access_restricted_modules,
    )


@router.get("/auth/me", response_model=UserResponse, summary="Get authenticated user profile")
async def api_me(current_user: User = Depends(require_api_auth)):
    return current_user


@router.post("/auth/logout", summary="Revoke all currently issued tokens")
async def api_logout(
    current_user: User = Depends(require_api_auth),
    db: Session = Depends(get_db),
):
    current_user.token_version += 1
    db.commit()
    return {"message": "Logged out successfully"}
