import logging
import smtplib
from typing import Optional
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)


def get_smtp_config_from_db(db: Session) -> dict:
    """Fetch stored SMTP configuration from database system_configuration or env defaults."""
    from sqlalchemy import text
    try:
        row = db.execute(text("SELECT smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_use_tls FROM system_configuration LIMIT 1")).fetchone()
        if row and row[0]:
            pwd = row[3] or ""
            if pwd.startswith("gAAAAA"):  # Fernet encrypted
                try:
                    pwd = decrypt(pwd)
                except Exception:
                    pass
            return {
                "host": row[0],
                "port": int(row[1] or 587),
                "user": row[2] or "",
                "password": pwd,
                "from_email": row[4] or row[2] or "noreply@safar.com",
                "use_tls": bool(row[5]) if row[5] is not None else True,
            }
    except Exception as exc:
        logger.warning("Error fetching SMTP config from DB: %s", exc)

    return {
        "host": "smtp.gmail.com",
        "port": 587,
        "user": "",
        "password": "",
        "from_email": "noreply@safar.com",
        "use_tls": True,
    }


def send_email_via_db_smtp(to_email: str, subject: str, body_html: str, db: Optional[Session] = None) -> bool:
    """Dispatches HTML email via database-configured SMTP settings."""
    close_session = False
    if db is None:
        db = SessionLocal()
        close_session = True

    try:
        config = get_smtp_config_from_db(db)
        if not config["host"]:
            logger.warning("SMTP host not configured. Email to %s skipped.", to_email)
            return False

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = config["from_email"]
        msg["To"] = to_email

        html_part = MIMEText(body_html, "html")
        msg.attach(html_part)

        server = smtplib.SMTP(config["host"], config["port"], timeout=15)
        if config["use_tls"]:
            server.starttls()

        if config["user"] and config["password"]:
            server.login(config["user"], config["password"])

        server.sendmail(config["from_email"], [to_email], msg.as_string())
        server.quit()
        logger.info("Email successfully sent to %s (Subject: %s)", to_email, subject)
        return True
    except Exception as exc:
        logger.error("Failed to send email to %s: %s", to_email, exc)
        return False
    finally:
        if close_session:
            db.close()
