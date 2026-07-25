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


from app.models.alert import Alert, AlertSeverity, AlertType


def authenticate_user(db: Session, login: str, password: str) -> Optional[User]:
    """Authenticate System Admin strictly against .env settings. All non-admin users must authenticate via OTP."""
    # Check if login is for admin
    if login == settings.admin_username:
        if password == settings.admin_password:
            return get_or_create_single_admin(db)
        else:
            logger.warning("Failed admin login attempt for username '%s'", login)
            return None

    # For non-admin users, passwords are removed. Authentication MUST happen via Email OTP.
    logger.info("Non-admin user '%s' attempted password login. Direct password auth disabled — use OTP authentication.", login)
    return None


def generate_and_send_user_otp(db: Session, login_or_email: str) -> Dict[str, Any]:
    """Generate a 6-digit OTP code, log it to Admin Alerts, and dispatch via email."""
    user = (
        db.query(User)
        .filter((User.email == login_or_email) | (User.username == login_or_email) | (User.phone == login_or_email))
        .first()
    )
    if not user or not user.is_active:
        return {"success": False, "error": "Registered user account not found or inactive."}

    if user.role == UserRole.admin:
        return {"success": False, "error": "System Admin must authenticate via .env credentials."}

    user_email = user.email or f"{user.username}@sastrybalm.local"
    otp_code = f"{random.randint(100000, 999999)}"
    expires_at = datetime.utcnow() + timedelta(minutes=10)

    # Deactivate prior unused OTPs for this user
    db.query(UserOTP).filter(UserOTP.user_id == user.id, UserOTP.is_used == False).update({"is_used": True})

    otp_record = UserOTP(
        user_id=user.id,
        email=user_email,
        otp_code=otp_code,
        expires_at=expires_at,
        is_used=False,
    )
    db.add(otp_record)

    # Create an Admin Alert record so OTP is visible in Admin Dashboard logs
    admin_alert = Alert(
        severity=AlertSeverity.info,
        alert_type=AlertType.custom,
        title=f"Login OTP for {user.full_name or user.username}",
        message=f"OTP verification code for user '{user.username}' ({user_email}): {otp_code} (Valid for 10 minutes)",
    )
    db.add(admin_alert)
    db.commit()

    # Send HTML Email if SMTP configured
    sent = False
    if user.email and "@" in user.email:
        subject = f"Your Sastrybalm Login OTP: {otp_code}"
        body_html = f"""
        <div style="font-family: Arial, sans-serif; max-width: 500px; margin: 0 auto; padding: 20px; border: 1px solid #e2e8f0; border-radius: 12px;">
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

    logger.info("OTP generated for user '%s': %s (Email sent: %s)", user.username, otp_code, sent)

    return {
        "success": True,
        "message": f"OTP code sent to {user_email}.",
        "email": user_email,
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
