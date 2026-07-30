import logging
import os
import secrets
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.models.user import User, UserRole
from app.models.user_otp import UserOTP
from app.utils.email import send_email_via_db_smtp
from app.utils.security import hash_password, verify_password

logger = logging.getLogger(__name__)


from app.utils.backup_service import restore_sql_backup


def is_system_onboarded(db: Session) -> bool:
    """Check if the system has completed onboarding (active admin or user with encrypted password)."""
    try:
        if db.query(User).count() == 0:
            return False
        admin = db.query(User).filter(User.role == UserRole.admin, User.is_active == True).first()
        if not admin:
            admin = db.query(User).filter(User.role == UserRole.admin).first()
        if not admin:
            admin = db.query(User).filter(User.is_active == True).first()
        if not admin:
            admin = db.query(User).first()
        return bool(admin and admin.hashed_password and admin.hashed_password.strip() != "" and admin.hashed_password != "PENDING_ONBOARDING")
    except Exception as e:
        logger.error(f"is_system_onboarded check exception: {e}", exc_info=True)
        return False


def complete_system_onboarding(
    db: Session,
    username: str,
    full_name: str,
    email: str,
    phone: str,
    password: str,
    backup_file_path: Optional[str] = None,
) -> User:
    """Perform first-bootup system onboarding: optionally restore .sql backup and save Admin password."""
    # 1. Restore backup data if provided
    if backup_file_path and os.path.exists(backup_file_path):
        try:
            restore_sql_backup(backup_file_path, db=db)
        except Exception as e:
            logger.error("Error restoring backup during onboarding: %s", e)

    # 3. Get or create Admin user in users table
    admin = db.query(User).filter(User.role == UserRole.admin).first()
    if not admin:
        admin = db.query(User).filter(User.username == username.strip()).first()

    phone_clean = phone.strip() if phone and phone.strip() else "9999999999"

    if not admin:
        admin = User(
            username=username.strip(),
            full_name=full_name.strip() or "System Administrator",
            email=email.strip() or "admin@safar.com",
            phone=phone_clean,
            role=UserRole.admin,
            is_active=True,
            hashed_password=hash_password(password),
        )
        db.add(admin)
    else:
        admin.username = username.strip()
        admin.full_name = full_name.strip() or admin.full_name
        admin.email = email.strip() or admin.email
        admin.phone = phone_clean
        admin.role = UserRole.admin
        admin.is_active = True
        admin.hashed_password = hash_password(password)

    db.commit()
    db.refresh(admin)
    logger.info("System onboarding completed with mandatory S3. Admin user '%s' saved.", admin.username)
    return admin


from app.models.alert import Alert, AlertSeverity, AlertType


def authenticate_user(db: Session, login: str, password: str) -> Optional[User]:
    """Authenticate System Admin against encrypted hashed password in users table."""
    user = (
        db.query(User)
        .filter((User.username == login) | (User.email == login) | (User.phone == login))
        .first()
    )
    if not user or not user.is_active:
        return None

    if user.hashed_password and verify_password(password, user.hashed_password):
        return user
    logger.warning("Failed login attempt for user_id=%s", user.id)
    return None


OTP_REQUEST_LIMIT = 3
OTP_ATTEMPT_LIMIT = 5
OTP_TTL_MINUTES = 10
OTP_THROTTLE_MINUTES = 15


def _find_login_user(db: Session, login: str) -> Optional[User]:
    return (
        db.query(User)
        .filter(
            (User.email == login)
            | (User.username == login)
            | (User.phone == login)
        )
        .first()
    )


def generate_and_send_user_otp(db: Session, login_or_email: str) -> Dict[str, Any]:
    """Issue a hashed, rate-limited OTP and deliver it only through SMTP."""
    user = _find_login_user(db, login_or_email)
    if not user or not user.is_active:
        return {"success": False, "error": "Registered user account not found or inactive."}
    if user.role == UserRole.admin:
        return {"success": False, "error": "System Admin must authenticate via password."}

    throttle_since = datetime.utcnow() - timedelta(minutes=OTP_THROTTLE_MINUTES)
    recent_count = (
        db.query(UserOTP)
        .filter(
            UserOTP.user_id == user.id,
            UserOTP.created_at >= throttle_since,
        )
        .count()
    )
    if recent_count >= OTP_REQUEST_LIMIT:
        return {
            "success": False,
            "error": "Too many OTP requests. Please wait before trying again.",
        }

    otp_code = f"{secrets.randbelow(900000) + 100000:06d}"
    db.query(UserOTP).filter(
        UserOTP.user_id == user.id,
        UserOTP.is_used.is_(False),
    ).update({"is_used": True})
    record = UserOTP(
        user_id=user.id,
        email=user.email,
        otp_code=hash_password(otp_code),
        failed_attempts=0,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_TTL_MINUTES),
        is_used=False,
    )
    db.add(record)
    db.flush()

    body_html = (
        "<h2>Safar verification code</h2>"
        f"<p>Hello {user.full_name or user.username},</p>"
        f"<p>Your one-time login code is <strong>{otp_code}</strong>.</p>"
        f"<p>It expires in {OTP_TTL_MINUTES} minutes. Do not share it.</p>"
    )
    delivered = send_email_via_db_smtp(
        to_email=user.email,
        subject="Your Safar login verification code",
        body_html=body_html,
        db=db,
    )
    if not delivered:
        db.rollback()
        return {"success": False, "error": "OTP email delivery failed. Please contact support."}

    db.commit()
    logger.info("OTP issued and delivered for user_id=%s (OTP: %s)", user.id, otp_code)
    return {
        "success": True,
        "message": "OTP verification code sent.",
        "email": user.email,
        "email_sent": True,
    }


def verify_user_otp(db: Session, email_or_login: str, otp_code: str) -> Optional[User]:
    """Verify the latest active OTP with a fixed attempt limit."""
    user = _find_login_user(db, email_or_login)
    if not user or not user.is_active or user.role == UserRole.admin:
        return None
    record = (
        db.query(UserOTP)
        .filter(
            UserOTP.user_id == user.id,
            UserOTP.is_used.is_(False),
            UserOTP.expires_at >= datetime.utcnow(),
        )
        .order_by(UserOTP.created_at.desc())
        .first()
    )
    if not record:
        return None
    if record.failed_attempts >= OTP_ATTEMPT_LIMIT:
        record.is_used = True
        db.commit()
        return None
    if not verify_password(otp_code, record.otp_code):
        record.failed_attempts += 1
        if record.failed_attempts >= OTP_ATTEMPT_LIMIT:
            record.is_used = True
        db.commit()
        return None
    record.is_used = True
    db.commit()
    return user
