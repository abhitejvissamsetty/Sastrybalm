import logging
import os
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


from app.utils.backup_service import restore_sql_backup


def is_system_onboarded(db: Session) -> bool:
    """Check if the system has completed onboarding (active admin with encrypted password)."""
    try:
        admin = db.query(User).filter(User.role == UserRole.admin, User.is_active == True).first()
        return bool(admin and admin.hashed_password and admin.hashed_password.strip() != "" and admin.hashed_password != "PENDING_ONBOARDING")
    except Exception as e:
        logger.warning(f"is_system_onboarded check exception: {e}")
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
            restore_sql_backup(backup_file_path)
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
            email=email.strip() or "admin@sastrybalm.com",
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

    if user.role == UserRole.admin:
        if user.hashed_password and verify_password(password, user.hashed_password):
            return user
        logger.warning("Failed admin login attempt for '%s'", login)
        return None

    # For non-admin users, passwords are not used — authentication is via OTP
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
        return {"success": False, "error": "System Admin must authenticate via password."}

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

    # Create an Alert record bound to the specific user (visible to user & Admin)
    admin_alert = Alert(
        severity=AlertSeverity.info,
        alert_type=AlertType.custom,
        title=f"Login OTP for {user.full_name or user.username}",
        message=f"OTP verification code for user '{user.username}' ({user_email}): {otp_code} (Valid for 10 minutes)",
        user_id=user.id,
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
