"""
Startup Validation Service — Executed on FastAPI lifespan startup to verify:
1. Active Admin user account exists in system.
2. S3/MinIO configuration settings exist and connectivity to bucket is functional.
"""
import logging
from typing import Optional
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models.user import User, UserRole

logger = logging.getLogger("sastrybalm.startup")


def validate_admin_account(db: Session) -> bool:
    """Verify at least one active Admin user exists."""
    admin = db.query(User).filter(
        User.role == UserRole.admin,
        User.is_active == True
    ).first()
    if admin:
        logger.info(f"Startup check: Active Admin account found ({admin.username} / {admin.email}).")
        return True
    else:
        logger.warning("Startup check WARNING: No active Admin user account found in database!")
        return False


def validate_s3_configuration(db: Session) -> dict:
    """Check S3/MinIO credentials and attempt a basic health check ping."""
    from app.models.company import SystemConfiguration, SystemSetting

    settings = {}
    sys_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    if sys_config:
        settings["s3_endpoint"] = sys_config.s3_endpoint_url
        settings["s3_bucket"] = sys_config.s3_bucket_name
        settings["s3_access_key"] = sys_config.s3_access_key_id
        settings["s3_secret_key"] = sys_config.s3_secret_access_key
        settings["s3_region"] = sys_config.s3_region_name

    # Fallback/override check SystemSetting table
    setting_keys = ["s3_endpoint", "s3_bucket", "s3_access_key", "s3_secret_key", "s3_region", "s3_use_ssl"]
    for key in setting_keys:
        s = db.query(SystemSetting).filter(SystemSetting.key == key).first()
        if s and s.value:
            settings[key] = s.value

    bucket = settings.get("s3_bucket")
    access_key = settings.get("s3_access_key")

    if not bucket or not access_key:
        logger.warning("Startup check WARNING: S3/MinIO storage is not configured! Uploads will default to local storage.")
        return {"configured": False, "status": "Not configured", "settings": settings}

    try:
        from app.adapters.s3_storage import test_s3_connection
        success, msg = test_s3_connection(settings)
        if success:
            logger.info(f"Startup check: S3/MinIO bucket '{bucket}' connectivity verified successfully.")
            return {"configured": True, "status": "Verified", "message": msg, "settings": settings}
        else:
            logger.warning(f"Startup check WARNING: S3/MinIO connection failed: {msg}")
            return {"configured": True, "status": "Connection failed", "message": msg, "settings": settings}
    except Exception as e:
        logger.warning(f"Startup check WARNING: Error during S3 connectivity test: {e}")
        return {"configured": True, "status": f"Error: {e}", "settings": settings}


def validate_admin_and_s3_config():
    """Main entrypoint for application lifespan startup validation."""
    db = SessionLocal()
    try:
        admin_ok = validate_admin_account(db)
        s3_res = validate_s3_configuration(db)
        return {
            "admin_ok": admin_ok,
            "s3_status": s3_res
        }
    finally:
        db.close()
