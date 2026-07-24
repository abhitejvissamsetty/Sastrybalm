import logging
import random
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User, UserRole
from app.models.user_otp import UserOTP
from app.utils.email import send_email_via_db_smtp
from app.utils.security import hash_password, verify_password

logger = logging.getLogger(__name__)


def get_or_create_single_admin(db: Session) -> User:
    """Ensure strictly ONLY ONE single admin exists in the system aligned with .env credentials."""
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if not admin:
        admin = db.query(User).filter(User.username == settings.admin_username).first()

    if not admin:
        admin = User(
            username=settings.admin_username,
            email="admin@sastrybalm.com",
            full_name="System Administrator",
            role=UserRole.admin,
            is_active=True,
            hashed_password=hash_password(settings.admin_password),
        )
        db.add(admin)
        db.commit()
        db.refresh(admin)
    else:
        # Sync admin attributes with .env configuration
        admin.username = settings.admin_username
        admin.role = UserRole.admin
        admin.is_active = True
        admin.hashed_password = hash_password(settings.admin_password)
        db.commit()

    return admin


def authenticate_user(db: Session, login: str, password: str) -> Optional[User]:
    """Authenticate Admin strictly against .env settings, or verify regular password."""
    # Check if login is for admin
    if login == settings.admin_username:
        if password == settings.admin_password:
            return get_or_create_single_admin(db)
        else:
            logger.warning("Failed admin login attempt for username '%s'", login)
            return None

    # Check for non-admin user
    user = (
        db.query(User)
        .filter((User.username == login) | (User.email == login) | (User.phone == login))
        .first()
    )
    if not user or not user.is_active:
        return None

    # If an admin user in DB tries to log in with DB password, enforce .env auth
    if user.role == UserRole.admin:
        if login == settings.admin_username and password == settings.admin_password:
            return get_or_create_single_admin(db)
        return None

    if verify_password(password, user.hashed_password):
        return user

    return None


def generate_and_send_user_otp(db: Session, login_or_email: str) -> Dict[str, Any]:
    """Generate a 6-digit OTP code and dispatch it to the user's email address."""
    user = (
        db.query(User)
        .filter((User.email == login_or_email) | (User.username == login_or_email) | (User.phone == login_or_email))
        .first()
    )
    if not user or not user.is_active:
        return {"success": False, "error": "Registered user account not found or inactive."}

    if user.role == UserRole.admin:
        return {"success": False, "error": "System Admin must authenticate via .env credentials."}

    if not user.email or "@" not in user.email:
        return {"success": False, "error": f"No valid email address registered for user '{user.username}'."}

    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Deactivate prior unused OTPs for this user
    db.query(UserOTP).filter(UserOTP.user_id == user.id, UserOTP.is_used == False).update({"is_used": True})

    otp_record = UserOTP(
        user_id=user.id,
        email=user.email,
        otp_code=otp_code,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(otp_record)
    db.commit()

    # Send HTML Email
    subject = f"Your Sastrybalm Login OTP: {otp_code}"
    body_html = f"""
    <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; rounded: 12px;">
      <h2 style="color: #4f46e5; margin-top: 0;">Sastrybalm SFA Verification Code</h2>
      <p style="font-size: 15px; color: #334155;">Hello <strong>{user.full_name or user.username}</strong>,</p>
      <p style="font-size: 14px; color: #475569;">Use the following 6-digit One-Time Password (OTP) to securely log in to your Sastrybalm SFA portal:</p>
      <div style="background-color: #f1f5f9; padding: 15px; text-align: center; border-radius: 8px; margin: 20px 0;">
        <span style="font-family: monospace; font-size: 32px; font-weight: bold; letter-spacing: 6px; color: #1e1b4b;">{otp_code}</span>
      </div>
      <p style="font-size: 13px; color: #64748b;">This OTP code is valid for <strong>10 minutes</strong>. Do not share this code with anyone.</p>
    </div>
    """
    sent = send_email_via_db_smtp(to_email=user.email, subject=subject, body_html=body_html, db=db)

    return {
        "success": True,
        "email": user.email,
        "username": user.username,
        "otp_code": otp_code,
        "email_sent": sent,
    }


def verify_user_otp(db: Session, email_or_login: str, otp_code: str) -> Optional[User]:
    """Verify an active 6-digit OTP code for user login."""
    user = (
        db.query(User)
        .filter((User.email == email_or_login) | (User.username == email_or_login) | (User.phone == email_or_login))
        .first()
    )
    if not user or not user.is_active:
        return None

    now = datetime.utcnow()
    record = (
        db.query(UserOTP)
        .filter(
            UserOTP.user_id == user.id,
            UserOTP.otp_code == otp_code,
            UserOTP.is_used == False,
            UserOTP.expires_at >= now,
        )
        .order_by(UserOTP.created_at.desc())
        .first()
    )

    if not record:
        return None

    record.is_used = True
    db.commit()
    return user
