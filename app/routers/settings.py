import logging
import json
import smtplib
import urllib.request
import urllib.parse
from datetime import datetime
from email.mime.text import MIMEText
from typing import Optional

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.dependencies import get_db, require_web_roles
from app.models.user import User, UserRole
from app.models.webhook import SystemWebhook, WebhookEvent
from app.models.beat_type import BeatTypeMaster
from app.utils.beat_types import seed_default_beat_types
from app.utils.encryption import encrypt, decrypt
from app.utils.flash import get_flash, set_flash_error, set_flash_success

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/settings", tags=["settings"])
templates = Jinja2Templates(directory="app/templates")


@router.get("/smtp", response_class=HTMLResponse)
async def smtp_settings_form(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Admin interface to view and edit database-stored SMTP settings."""
    smtp_config = {
        "smtp_host": "",
        "smtp_port": "587",
        "smtp_user": "",
        "smtp_password": "",
        "smtp_from": "noreply@sastrybalm.com",
        "smtp_use_tls": True,
    }
    try:
        row = db.execute(text("SELECT smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_use_tls FROM system_configuration WHERE id = 1 LIMIT 1")).fetchone()
        if not row:
            db.execute(text("INSERT IGNORE INTO system_configuration (id) VALUES (1)"))
            db.commit()
            row = db.execute(text("SELECT smtp_host, smtp_port, smtp_user, smtp_password, smtp_from, smtp_use_tls FROM system_configuration WHERE id = 1 LIMIT 1")).fetchone()

        if row:
            pwd = row[3] or ""
            if pwd.startswith("gAAAAA"):
                try:
                    pwd = decrypt(pwd)
                except Exception:
                    pass
            smtp_config = {
                "smtp_host": row[0] or "",
                "smtp_port": str(row[1] or 587),
                "smtp_user": row[2] or "",
                "smtp_password": pwd,
                "smtp_from": row[4] or "noreply@sastrybalm.com",
                "smtp_use_tls": bool(row[5]) if row[5] is not None else True,
            }
    except Exception as exc:
        logger.warning("Error loading SMTP settings from DB: %s", exc)

    return templates.TemplateResponse("settings/smtp.html", {
        "request": request,
        "current_user": current_user,
        "smtp": smtp_config,
        **get_flash(request),
    })


@router.post("/smtp")
async def smtp_settings_save(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    smtp_host: str = Form(""),
    smtp_port: int = Form(587),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from: str = Form("noreply@sastrybalm.com"),
    smtp_use_tls: Optional[str] = Form(default=None),
):
    """Save SMTP settings into database system_configuration table with UPSERT guarantee."""
    encrypted_pwd = encrypt(smtp_password) if smtp_password else ""
    use_tls_val = 1 if smtp_use_tls else 0
    try:
        db.execute(text("INSERT IGNORE INTO system_configuration (id) VALUES (1)"))
        db.execute(text("""
            UPDATE system_configuration SET 
                smtp_host = :host,
                smtp_port = :port,
                smtp_user = :user,
                smtp_password = :pwd,
                smtp_from = :from_email,
                smtp_use_tls = :use_tls
            WHERE id = 1
        """), {
            "host": smtp_host,
            "port": smtp_port,
            "user": smtp_user,
            "pwd": encrypted_pwd,
            "from_email": smtp_from,
            "use_tls": use_tls_val,
        })
        db.commit()
        set_flash_success(request, f"SMTP settings for '{smtp_host}' successfully saved to database.")
    except Exception as exc:
        db.rollback()
        set_flash_error(request, f"Failed to save SMTP settings: {exc}")

    return RedirectResponse("/settings/smtp", status_code=302)


@router.post("/smtp/test")
async def smtp_settings_test(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    smtp_host: str = Form(""),
    smtp_port: int = Form(587),
    smtp_user: str = Form(""),
    smtp_password: str = Form(""),
    smtp_from: str = Form("noreply@sastrybalm.com"),
    smtp_use_tls: Optional[str] = Form(default=None),
):
    """Test SMTP Connection and send a test email verification."""
    if not smtp_host:
        set_flash_error(request, "SMTP Host cannot be empty.")
        return RedirectResponse("/settings/smtp", status_code=302)

    use_tls = bool(smtp_use_tls)
    try:
        server = smtplib.SMTP(smtp_host, smtp_port, timeout=8)
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()

        if smtp_user and smtp_password:
            server.login(smtp_user, smtp_password)

        test_recipient = current_user.email or smtp_from or smtp_user
        if test_recipient:
            msg = MIMEText(f"Hello {current_user.full_name},\n\nThis is a test email sent from Sastrybalm SFA to verify your SMTP server configuration.\n\nTime: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}")
            msg["Subject"] = "Sastrybalm SFA — Test SMTP Connection Successful"
            msg["From"] = smtp_from or smtp_user
            msg["To"] = test_recipient
            server.sendmail(smtp_from or smtp_user, [test_recipient], msg.as_string())

        server.quit()
        set_flash_success(request, f"SMTP Connection Successful! Connected to '{smtp_host}:{smtp_port}' and sent test email to '{test_recipient}'.")
    except Exception as exc:
        logger.warning("SMTP test connection error for %s:%s: %s", smtp_host, smtp_port, exc)
        set_flash_error(request, f"SMTP Test Connection Failed: {exc}")

    return RedirectResponse("/settings/smtp", status_code=302)


# ── Sales Channels Master Configuration ───────────────────────────────────

@router.get("/beat-types")
async def beat_types_legacy_redirect():
    return RedirectResponse("/settings/sales-channels", status_code=301)


@router.get("/sales-channels", response_class=HTMLResponse)
async def sales_channels_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    seed_default_beat_types(db)
    items = db.query(BeatTypeMaster).order_by(BeatTypeMaster.name).all()
    return templates.TemplateResponse("settings/sales_channels.html", {
        "request": request,
        "current_user": current_user,
        "items": items,
        **get_flash(request),
    })


@router.post("/sales-channels/new")
async def sales_channels_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    description: Optional[str] = Form(default=None),
):
    code_clean = code.strip().upper()
    existing = db.query(BeatTypeMaster).filter(BeatTypeMaster.code == code_clean).first()
    if existing:
        set_flash_error(request, f"Sales channel with code '{code_clean}' already exists.")
        return RedirectResponse("/settings/sales-channels", status_code=302)

    bt = BeatTypeMaster(
        code=code_clean,
        name=name.strip(),
        description=description.strip() if description else None,
        is_active=True
    )
    db.add(bt)
    db.commit()
    set_flash_success(request, f"Sales channel '{name}' created successfully.")
    return RedirectResponse("/settings/sales-channels", status_code=302)


@router.post("/sales-channels/{bt_id}/toggle")
async def sales_channels_toggle(
    bt_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    bt = db.query(BeatTypeMaster).filter(BeatTypeMaster.id == bt_id).first()
    if bt:
        bt.is_active = not bt.is_active
        db.commit()
        state = "activated" if bt.is_active else "deactivated"
        set_flash_success(request, f"Sales channel '{bt.name}' {state}.")
    return RedirectResponse("/settings/sales-channels", status_code=302)


@router.post("/sales-channels/{bt_id}/delete")
async def sales_channels_delete(
    bt_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    bt = db.query(BeatTypeMaster).filter(BeatTypeMaster.id == bt_id).first()
    if bt:
        db.delete(bt)
        db.commit()
        set_flash_success(request, f"Sales channel '{bt.name}' deleted.")
    return RedirectResponse("/settings/sales-channels", status_code=302)


# ── Warehouses Master Configuration ─────────────────────────────────────

@router.get("/warehouses", response_class=HTMLResponse)
async def warehouses_list(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.models.warehouse import Warehouse
    warehouses = db.query(Warehouse).order_by(Warehouse.name).all()

    # Seed default if empty
    if not warehouses:
        default_wh = Warehouse(
            code="WH-MAIN",
            name="Main Central Depot",
            address="Central Operations Hub",
            pincode="500001",
            is_active=True
        )
        db.add(default_wh)
        db.commit()
        warehouses = db.query(Warehouse).order_by(Warehouse.name).all()

    return templates.TemplateResponse("settings/warehouses.html", {
        "request": request,
        "current_user": current_user,
        "warehouses": warehouses,
        **get_flash(request),
    })


@router.post("/warehouses/new")
async def warehouses_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    code: str = Form(...),
    address: Optional[str] = Form(default=None),
    pincode: Optional[str] = Form(default=None),
    contact_person: Optional[str] = Form(default=None),
    mobile: Optional[str] = Form(default=None),
):
    from app.models.warehouse import Warehouse
    code_clean = code.strip().upper()
    existing = db.query(Warehouse).filter(Warehouse.code == code_clean).first()
    if existing:
        set_flash_error(request, f"Warehouse with code '{code_clean}' already exists.")
        return RedirectResponse("/settings/warehouses", status_code=302)

    wh = Warehouse(
        code=code_clean,
        name=name.strip(),
        address=address.strip() if address else None,
        pincode=pincode.strip() if pincode else None,
        contact_person=contact_person.strip() if contact_person else None,
        mobile=mobile.strip() if mobile else None,
        is_active=True
    )
    db.add(wh)
    db.commit()
    set_flash_success(request, f"Warehouse '{name}' created successfully.")
    return RedirectResponse("/settings/warehouses", status_code=302)


@router.post("/warehouses/{wh_id}/toggle")
async def warehouses_toggle(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.models.warehouse import Warehouse
    wh = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if wh:
        wh.is_active = not wh.is_active
        db.commit()
        state = "activated" if wh.is_active else "deactivated"
        set_flash_success(request, f"Warehouse '{wh.name}' {state}.")
    return RedirectResponse("/settings/warehouses", status_code=302)


@router.post("/warehouses/{wh_id}/delete")
async def warehouses_delete(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    from app.models.warehouse import Warehouse
    wh = db.query(Warehouse).filter(Warehouse.id == wh_id).first()
    if wh:
        db.delete(wh)
        db.commit()
        set_flash_success(request, f"Warehouse '{wh.name}' deleted.")
    return RedirectResponse("/settings/warehouses", status_code=302)


# ── Webhooks Management ──────────────────────────────────────────────────

@router.get("/webhooks", response_class=HTMLResponse)
async def webhooks_settings_form(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    webhooks = db.query(SystemWebhook).order_by(SystemWebhook.created_at.desc()).all()
    return templates.TemplateResponse("settings/webhooks.html", {
        "request": request,
        "current_user": current_user,
        "webhooks": webhooks,
        "WebhookEvent": WebhookEvent,
        **get_flash(request),
    })


@router.post("/webhooks/new")
async def webhook_create(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
    name: str = Form(...),
    event_type: str = Form(...),
    endpoint_url: str = Form(...),
    secret_key: Optional[str] = Form(default=None),
):
    if event_type not in [e.value for e in WebhookEvent]:
        set_flash_error(request, f"Invalid event type '{event_type}'.")
        return RedirectResponse("/settings/webhooks", status_code=302)

    wh = SystemWebhook(
        name=name,
        event_type=WebhookEvent(event_type),
        endpoint_url=endpoint_url,
        secret_key=secret_key or None,
        is_active=True,
    )
    db.add(wh)
    db.commit()
    set_flash_success(request, f"Webhook '{name}' created for event '{event_type}'.")
    return RedirectResponse("/settings/webhooks", status_code=302)


@router.post("/webhooks/{wh_id}/toggle")
async def webhook_toggle(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    wh = db.query(SystemWebhook).filter(SystemWebhook.id == wh_id).first()
    if wh:
        wh.is_active = not wh.is_active
        db.commit()
        state = "activated" if wh.is_active else "deactivated"
        set_flash_success(request, f"Webhook '{wh.name}' {state}.")
    return RedirectResponse("/settings/webhooks", status_code=302)


@router.post("/webhooks/{wh_id}/delete")
async def webhook_delete(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    wh = db.query(SystemWebhook).filter(SystemWebhook.id == wh_id).first()
    if wh:
        db.delete(wh)
        db.commit()
        set_flash_success(request, f"Webhook '{wh.name}' deleted.")
    return RedirectResponse("/settings/webhooks", status_code=302)


@router.post("/webhooks/{wh_id}/test")
async def webhook_test(
    wh_id: int,
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
    db: Session = Depends(get_db),
):
    """Trigger a test payload to the webhook endpoint URL."""
    wh = db.query(SystemWebhook).filter(SystemWebhook.id == wh_id).first()
    if not wh:
        set_flash_error(request, "Webhook not found.")
        return RedirectResponse("/settings/webhooks", status_code=302)

    payload = {
        "event": wh.event_type.value,
        "timestamp": datetime.utcnow().isoformat(),
        "test": True,
        "webhook_id": wh.id,
        "message": f"Test delivery for Sastrybalm SFA event '{wh.event_type.value}'",
        "data": {
            "sample_order_number": "ORD-TEST-9901",
            "sample_amount": 1500.00,
            "outlet_name": "Sample Retail Store",
        }
    }
    
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        wh.endpoint_url,
        data=data_bytes,
        headers={"Content-Type": "application/json", "User-Agent": "SastrybalmSFA-Webhook/1.0"},
        method="POST"
    )

    try:
        with urllib.request.urlopen(req, timeout=5) as response:
            status_code = response.getcode()
            wh.last_triggered_at = datetime.utcnow()
            db.commit()
            set_flash_success(request, f"Test payload sent to '{wh.endpoint_url}'. Received Response: HTTP {status_code}.")
    except Exception as exc:
        logger.warning("Webhook test error for %s: %s", wh.endpoint_url, exc)
        wh.last_triggered_at = datetime.utcnow()
        db.commit()
        set_flash_error(request, f"Test delivery to '{wh.endpoint_url}' failed: {exc}")

    return RedirectResponse("/settings/webhooks", status_code=302)


@router.get("/whatsapp", response_class=HTMLResponse)
async def whatsapp_settings_form(
    request: Request,
    current_user: User = Depends(require_web_roles(UserRole.admin)),
):
    return templates.TemplateResponse("settings/whatsapp.html", {
        "request": request,
        "current_user": current_user,
        **get_flash(request),
    })
