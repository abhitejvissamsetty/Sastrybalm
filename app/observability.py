"""Structured, redacted logging, request metrics, tracing, and error reporting."""

import contextvars
import hashlib
import hmac
import json
import logging
import os
import re
import time
import uuid
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import Response
from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
    multiprocess,
)

from app.config import settings

request_id_context = contextvars.ContextVar("request_id", default="-")
REQUEST_COUNT = Counter(
    "safar_http_requests_total",
    "HTTP requests",
    ("method", "route", "status"),
)
REQUEST_LATENCY = Histogram(
    "safar_http_request_duration_seconds",
    "HTTP request latency",
    ("method", "route"),
    buckets=(0.05, 0.1, 0.25, 0.5, 1, 2, 5, 10),
)
DB_POOL_CHECKED_OUT = Gauge(
    "safar_db_pool_checked_out",
    "Checked-out database connections",
    multiprocess_mode="livesum",
)
DB_POOL_CAPACITY = Gauge(
    "safar_db_pool_capacity",
    "Configured database pool plus overflow capacity",
    multiprocess_mode="livemax",
)
SCHEDULER_OWNER = Gauge(
    "safar_scheduler_owner",
    "One when a live scheduler owns the database lease",
    multiprocess_mode="livemax",
)

_SENSITIVE_KEYS = re.compile(
    r"(authorization|cookie|password|secret|token|otp|api[_-]?key|"
    r"email|phone|mobile|address|gps|latitude|longitude)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
_EMAIL = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


def redact(value: Any, key: str = "") -> Any:
    if _SENSITIVE_KEYS.search(key):
        return "[REDACTED]"
    if isinstance(value, dict):
        return {str(k): redact(v, str(k)) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [redact(item) for item in value]
    if isinstance(value, str):
        return _EMAIL.sub("[REDACTED_EMAIL]", _BEARER.sub("Bearer [REDACTED]", value))
    return value


class RedactingJsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        message = record.getMessage()
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
            "level": record.levelname,
            "logger": record.name,
            "message": redact(message),
            "request_id": request_id_context.get(),
        }
        if record.exc_info:
            payload["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(payload, separators=(",", ":"), default=str)


def configure_observability() -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(RedactingJsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.INFO)

    if settings.sentry_dsn:
        import sentry_sdk

        def before_send(event, _hint):
            event.pop("user", None)
            if "request" in event:
                event["request"].pop("data", None)
                event["request"].pop("cookies", None)
                event["request"]["headers"] = {}
                event["request"]["query_string"] = "[REDACTED]"
            return redact(event)

        sentry_sdk.init(
            dsn=settings.sentry_dsn,
            environment=settings.environment,
            traces_sample_rate=settings.sentry_traces_sample_rate,
            send_default_pii=False,
            before_send=before_send,
        )


def normalized_route(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", request.url.path)


async def observe_request(request: Request, call_next):
    incoming = request.headers.get("X-Request-ID", "")
    request_id = incoming[:128] if incoming else str(uuid.uuid4())
    token = request_id_context.set(request_id)
    started = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = normalized_route(request)
        elapsed = time.perf_counter() - started
        REQUEST_COUNT.labels(request.method, route, str(status)).inc()
        REQUEST_LATENCY.labels(request.method, route).observe(elapsed)
        logging.getLogger("safar.request").info(
            "request_complete method=%s route=%s status=%s duration_ms=%.2f",
            request.method,
            route,
            status,
            elapsed * 1000,
        )
        if "response" in locals():
            response.headers["X-Request-ID"] = request_id
            response.headers["Server-Timing"] = f"app;dur={elapsed * 1000:.2f}"
        request_id_context.reset(token)


def metrics_response(request: Request) -> Response:
    authorization = request.headers.get("Authorization", "")
    bearer = (
        authorization.removeprefix("Bearer ").strip()
        if authorization.startswith("Bearer ")
        else ""
    )
    supplied = bearer or request.headers.get("X-Metrics-Token", "")
    if not settings.metrics_token or not hmac.compare_digest(
        supplied, settings.metrics_token
    ):
        raise HTTPException(status_code=404, detail="Not found.")
    try:
        from datetime import datetime, timedelta
        from app.database import SessionLocal, engine
        from app.models.scheduler_state import SchedulerHeartbeat

        DB_POOL_CHECKED_OUT.set(engine.pool.checkedout())
        DB_POOL_CAPACITY.set(engine.pool.size() + engine.pool._max_overflow)
        db = SessionLocal()
        try:
            heartbeat = db.get(SchedulerHeartbeat, 1)
            is_live = bool(
                heartbeat
                and heartbeat.heartbeat_at
                and heartbeat.heartbeat_at >= datetime.utcnow() - timedelta(seconds=90)
            )
            SCHEDULER_OWNER.set(1 if is_live else 0)
        finally:
            db.close()
    except Exception:
        logging.getLogger(__name__).exception("metrics_runtime_gauge_refresh_failed")

    registry = CollectorRegistry()
    if os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        multiprocess.MultiProcessCollector(registry)
        payload = generate_latest(registry)
    else:
        payload = generate_latest()
    return Response(payload, media_type=CONTENT_TYPE_LATEST)


def anonymized_actor(user_id: int | None) -> str:
    if user_id is None:
        return "anonymous"
    return hashlib.sha256(
        f"{settings.secret_key}:{user_id}".encode()
    ).hexdigest()[:16]
