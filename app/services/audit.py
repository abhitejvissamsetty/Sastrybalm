import hashlib
import hmac
import json
import logging
from dataclasses import dataclass
from typing import Mapping, Optional

from fastapi import Request

from app.config import settings
from app.database import SessionLocal
from app.models.audit import AuditEvent

logger = logging.getLogger(__name__)

_PUBLIC_PATH_PREFIXES = ("/static", "/health/", "/metrics")
_AUTH_PATHS = ("/login", "/auth", "/api/auth", "/logout", "/api/logout")
_OBJECT_ID_KEYS = (
    "id", "user_id", "outlet_id", "order_id", "payment_id", "expense_id",
    "visit_id", "request_id", "vendor_id", "warehouse_id", "product_id",
    "beat_id", "position_id", "geography_id", "asset_id",
)


@dataclass(frozen=True)
class AuditData:
    actor_user_id: Optional[int]
    actor_hash: Optional[str]
    actor_role: Optional[str]
    ip_hash: Optional[str]
    action: str
    method: str
    route: str
    object_type: Optional[str]
    object_id: Optional[str]
    outcome: str
    status_code: int
    request_id: Optional[str]
    metadata_json: str = "{}"


def _keyed_hash(value: object) -> Optional[str]:
    if value is None or value == "":
        return None
    return hmac.new(
        settings.secret_key.encode("utf-8"),
        str(value).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def classify_action(method: str, route: str) -> str:
    route_lower = route.lower()
    if any(token in route_lower for token in ("/approve", "/reject", "approval")):
        return "approval"
    if any(token in route_lower for token in ("/export", ".csv", "/backup", "/download")):
        return "export"
    if any(token in route_lower for token in ("/settings", "/configuration", "/company")):
        return "configuration"
    if any(route_lower.startswith(path) for path in _AUTH_PATHS):
        return "authentication"
    return {
        "GET": "read",
        "HEAD": "read",
        "OPTIONS": "read",
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }.get(method.upper(), "other")


def build_audit_data(
    *,
    method: str,
    route: str,
    status_code: int,
    actor_user_id: Optional[int] = None,
    actor_role: Optional[str] = None,
    client_ip: Optional[str] = None,
    request_id: Optional[str] = None,
    path_params: Optional[Mapping[str, object]] = None,
) -> AuditData:
    params = path_params or {}
    object_key = next((key for key in _OBJECT_ID_KEYS if key in params), None)
    object_id = str(params[object_key])[:100] if object_key else None
    object_type = (
        object_key.removesuffix("_id") if object_key and object_key != "id"
        else route.strip("/").split("/")[0][:100] or None
    )
    return AuditData(
        actor_user_id=actor_user_id,
        actor_hash=_keyed_hash(actor_user_id),
        actor_role=actor_role[:50] if actor_role else None,
        ip_hash=_keyed_hash(client_ip),
        action=classify_action(method, route),
        method=method.upper()[:10],
        route=route[:255],
        object_type=object_type,
        object_id=object_id,
        outcome="success" if status_code < 400 else "denied" if status_code < 500 else "error",
        status_code=status_code,
        request_id=request_id[:100] if request_id else None,
        metadata_json=json.dumps({}, separators=(",", ":")),
    )


def persist_audit_data(data: AuditData) -> None:
    db = SessionLocal()
    try:
        db.add(AuditEvent(**data.__dict__))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("audit_event_persistence_failed")
    finally:
        db.close()


async def audit_request(request: Request, call_next):
    response = await call_next(request)
    route_object = request.scope.get("route")
    route = getattr(route_object, "path", request.url.path)
    is_authenticated = getattr(request.state, "audit_user_id", None) is not None
    is_auth_event = any(request.url.path.startswith(path) for path in _AUTH_PATHS)
    is_public = request.url.path.startswith(_PUBLIC_PATH_PREFIXES)
    if (is_authenticated or is_auth_event) and not is_public:
        client_ip = request.client.host if request.client else None
        data = build_audit_data(
            method=request.method,
            route=route,
            status_code=response.status_code,
            actor_user_id=getattr(request.state, "audit_user_id", None),
            actor_role=getattr(request.state, "audit_user_role", None),
            client_ip=client_ip,
            request_id=getattr(request.state, "request_id", None),
            path_params=request.path_params,
        )
        persist_audit_data(data)
    return response
