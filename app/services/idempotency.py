"""Database-backed idempotency for authenticated mobile mutations."""

import functools
import hashlib
import inspect
import json
from datetime import datetime

from fastapi import HTTPException
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError

from app.models.idempotency import IdempotencyRecord


def _serializable(value):
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, (str, int, float, bool, type(None))):
        return value
    if isinstance(value, (list, tuple)):
        return [_serializable(item) for item in value]
    if isinstance(value, dict):
        return {
            str(key): _serializable(item)
            for key, item in sorted(value.items(), key=lambda pair: str(pair[0]))
        }
    if hasattr(value, "filename"):
        return {
            "filename": getattr(value, "filename", None),
            "content_type": getattr(value, "content_type", None),
        }
    return str(value)


def _request_hash(arguments):
    payload = {
        key: _serializable(value)
        for key, value in arguments.items()
        if key not in {"db", "current_user", "idempotency_key"}
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()


def _claim(db, user_id, operation, key, request_hash):
    if not key or not key.strip():
        raise HTTPException(status_code=400, detail="Idempotency-Key is required.")
    key = key.strip()
    if len(key) > 128:
        raise HTTPException(status_code=400, detail="Idempotency-Key is too long.")

    record = IdempotencyRecord(
        user_id=user_id,
        operation=operation,
        idempotency_key=key,
        request_hash=request_hash,
        state="pending",
    )
    db.add(record)
    try:
        db.commit()
        db.refresh(record)
        return record, None
    except IntegrityError:
        db.rollback()

    existing = db.query(IdempotencyRecord).filter_by(
        user_id=user_id, operation=operation, idempotency_key=key
    ).one()
    if existing.request_hash != request_hash:
        raise HTTPException(
            status_code=409,
            detail="Idempotency-Key was already used for a different request.",
        )
    if existing.state == "completed" and existing.response_json:
        return existing, json.loads(existing.response_json)
    raise HTTPException(
        status_code=409,
        detail="An identical request with this Idempotency-Key is in progress.",
    )


def _complete(db, record, response):
    record.state = "completed"
    record.response_json = json.dumps(_serializable(response), sort_keys=True)
    record.completed_at = datetime.utcnow()
    db.commit()


def _abort(db, record):
    db.rollback()
    persisted = db.query(IdempotencyRecord).filter_by(id=record.id).first()
    if persisted and persisted.state == "pending":
        db.delete(persisted)
        db.commit()


def idempotent(operation):
    """Require a key, replay completed responses, and clean claims on failure."""

    def decorate(function):
        signature = inspect.signature(function)

        async def invoke_async(*args, **kwargs):
            bound = signature.bind_partial(*args, **kwargs)
            db = bound.arguments["db"]
            user = bound.arguments["current_user"]
            key = bound.arguments.get("idempotency_key")
            digest = _request_hash(bound.arguments)
            record, replay = _claim(db, user.id, operation, key, digest)
            if replay is not None:
                return replay
            try:
                response = await function(*args, **kwargs)
                _complete(db, record, response)
                return response
            except Exception:
                _abort(db, record)
                raise

        def invoke_sync(*args, **kwargs):
            bound = signature.bind_partial(*args, **kwargs)
            db = bound.arguments["db"]
            user = bound.arguments["current_user"]
            key = bound.arguments.get("idempotency_key")
            digest = _request_hash(bound.arguments)
            record, replay = _claim(db, user.id, operation, key, digest)
            if replay is not None:
                return replay
            try:
                response = function(*args, **kwargs)
                _complete(db, record, response)
                return response
            except Exception:
                _abort(db, record)
                raise

        wrapper = invoke_async if inspect.iscoroutinefunction(function) else invoke_sync
        return functools.wraps(function)(wrapper)

    return decorate
