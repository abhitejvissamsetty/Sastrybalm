import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

from sqlalchemy.orm import Session

from app.config import settings
from app.database import SessionLocal
from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)


def get_smtp_config_from_db(db: Session) -> dict:
    """Load encrypted database SMTP settings, falling back to environment settings."""
    from sqlalchemy import text

    try:
        row = db.execute(
            text(
                "SELECT smtp_host, smtp_port, smtp_user, smtp_password, "
                "smtp_from, smtp_use_tls FROM system_configuration LIMIT 1"
            )
        ).fetchone()
        if row and row[0]:
            password = row[3] or ""
            if password.startswith("gAAAAA"):
                password = decrypt(password)
            return {
                "host": row[0],
                "port": int(row[1] or 587),
                "user": row[2] or "",
                "password": password,
                "from_email": row[4] or row[2] or settings.smtp_from,
                "use_tls": bool(row[5]) if row[5] is not None else True,
            }
    except Exception as exc:
        logger.warning("Unable to load database SMTP configuration: %s", exc)

    return {
        "host": settings.smtp_host,
        "port": settings.smtp_port,
        "user": settings.smtp_user,
        "password": settings.smtp_password,
        "from_email": settings.smtp_from,
        "use_tls": True,
    }


def send_email_via_db_smtp(
    to_email: str,
    subject: str,
    body_html: str,
    db: Optional[Session] = None,
) -> bool:
    """Send an HTML email without logging credentials, message bodies, or OTP values."""
    owns_session = db is None
    if db is None:
        db = SessionLocal()
    try:
        config = get_smtp_config_from_db(db)
        if not config["host"]:
            logger.warning("SMTP is not configured; email delivery skipped")
            return False
        message = MIMEMultipart("alternative")
        message["Subject"] = subject
        message["From"] = config["from_email"]
        message["To"] = to_email
        message.attach(MIMEText(body_html, "html"))
        with smtplib.SMTP(config["host"], config["port"], timeout=15) as server:
            if config["use_tls"]:
                server.starttls()
            if config["user"] and config["password"]:
                server.login(config["user"], config["password"])
            server.sendmail(config["from_email"], [to_email], message.as_string())
        logger.info("Email delivered through configured SMTP service")
        return True
    except Exception:
        logger.exception("SMTP email delivery failed")
        return False
    finally:
        if owns_session:
            db.close()
