"""
Webhook receiver endpoints for external system callbacks.
Currently supports CMMS deployment status updates.
"""
import hmac
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.config import settings
from app.dependencies import get_db
from app.models.alert import Alert, AlertSeverity, AlertType
from app.models.material_request import MaterialRequest, MRStatus, MRSyncStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


class CMSWebhookPayload(BaseModel):
    """Expected payload from CMMS webhook callbacks."""
    work_order_id: str
    status: str  # e.g. "deployed", "failed", "in_progress"
    notes: Optional[str] = None
    idempotency_key: Optional[str] = None  # maps to mr_number


def _verify_webhook_secret(x_webhook_secret: Optional[str] = Header(default=None)) -> None:
    """Validate incoming webhook using shared secret from .env (CMMS_API_KEY)."""
    expected = settings.cmms_api_key
    if not expected:
        # No secret configured — allow all (dev mode)
        return
    if not x_webhook_secret or not hmac.compare_digest(x_webhook_secret, expected):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")


# ── Status mapping from CMMS terms → MRStatus ─────────────────────────────

CMMS_STATUS_MAP = {
    "acknowledged": MRStatus.acknowledged,
    "in_progress": MRStatus.in_progress,
    "completed": MRStatus.completed,
    "deployed": MRStatus.completed,
    "failed": MRStatus.cancelled,
    "cancelled": MRStatus.cancelled,
}


@router.post("/cmms")
async def cmms_webhook(
    payload: CMSWebhookPayload,
    db: Session = Depends(get_db),
    _auth: None = Depends(_verify_webhook_secret),
):
    """
    Receive deployment status updates from CMMS.
    Looks up the MaterialRequest by cmms_ref or idempotency_key (mr_number).
    """
    logger.info(
        "CMMS webhook received — work_order=%s status=%s key=%s",
        payload.work_order_id, payload.status, payload.idempotency_key,
    )

    # Find the matching material request
    mr = None
    if payload.idempotency_key:
        mr = db.query(MaterialRequest).filter(
            MaterialRequest.mr_number == payload.idempotency_key
        ).first()
    if not mr:
        mr = db.query(MaterialRequest).filter(
            MaterialRequest.cmms_ref == payload.work_order_id
        ).first()

    if not mr:
        logger.warning(
            "CMMS webhook: no matching MR for work_order=%s / key=%s",
            payload.work_order_id, payload.idempotency_key,
        )
        return {"status": "ignored", "reason": "no matching material request"}

    # Idempotency: skip if already at this status
    new_status = CMMS_STATUS_MAP.get(payload.status.lower())
    if new_status and mr.status == new_status:
        return {"status": "skipped", "reason": "already at this status"}

    # Update MR
    old_status = mr.status.value
    if new_status:
        mr.status = new_status
    mr.cmms_response = payload.notes or mr.cmms_response
    mr.cmms_ref = payload.work_order_id

    if payload.status.lower() in ("completed", "deployed"):
        mr.sync_status = MRSyncStatus.synced
    elif payload.status.lower() in ("failed", "cancelled"):
        mr.sync_status = MRSyncStatus.failed
        mr.sync_error = payload.notes

    # Create alert for status changes
    severity = AlertSeverity.info
    if payload.status.lower() in ("failed", "cancelled"):
        severity = AlertSeverity.critical
    elif payload.status.lower() in ("completed", "deployed"):
        severity = AlertSeverity.info

    db.add(Alert(
        severity=severity,
        alert_type=AlertType.cmms_status_change,
        title=f"CMMS update: {mr.mr_number} → {payload.status}",
        message=(
            f"Material request {mr.mr_number} status changed from "
            f"'{old_status}' to '{payload.status}' by CMMS. "
            f"Work order: {payload.work_order_id}."
            + (f" Notes: {payload.notes}" if payload.notes else "")
        ),
    ))

    db.commit()
    logger.info("CMMS webhook processed — MR %s: %s → %s", mr.mr_number, old_status, payload.status)

    return {"status": "ok", "mr_number": mr.mr_number, "new_status": mr.status.value}
