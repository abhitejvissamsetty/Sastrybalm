import asyncio
from datetime import timedelta

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials
from itsdangerous import SignatureExpired, TimestampSigner
from starlette.requests import Request

from app.dependencies import get_current_api_user, require_api_auth
from app.models.user_otp import UserOTP
from app.routers.api.auth import api_logout
from app.services.auth import (
    authenticate_user,
    generate_and_send_user_otp,
    verify_user_otp,
)
from app.utils.security import create_access_token, hash_password


def _credentials(token):
    return HTTPAuthorizationCredentials(scheme="Bearer", credentials=token)


def _request():
    return Request({"type": "http", "method": "GET", "path": "/", "headers": []})


def test_expired_and_versionless_tokens_are_rejected(db_session, acceptance_data):
    user = acceptance_data["users"]["admin"]
    expired = create_access_token(
        {"sub": str(user.id), "role": user.role.value, "ver": user.token_version},
        expires_delta=timedelta(seconds=-1),
    )
    legacy = create_access_token({"sub": str(user.id), "role": user.role.value})

    assert get_current_api_user(
        request=_request(), credentials=_credentials(expired), db=db_session
    ) is None
    assert get_current_api_user(
        request=_request(), credentials=_credentials(legacy), db=db_session
    ) is None


def test_logout_revokes_existing_token(db_session, acceptance_data):
    user = acceptance_data["users"]["admin"]
    token = create_access_token(
        {"sub": str(user.id), "role": user.role.value, "ver": user.token_version}
    )
    credentials = _credentials(token)
    assert get_current_api_user(
        request=_request(), credentials=credentials, db=db_session
    ).id == user.id

    asyncio.run(api_logout(current_user=user, db=db_session))

    assert get_current_api_user(
        request=_request(), credentials=credentials, db=db_session
    ) is None


def test_inactive_user_cannot_authenticate_or_use_token(db_session, acceptance_data):
    user = acceptance_data["users"]["admin"]
    token = create_access_token(
        {"sub": str(user.id), "role": user.role.value, "ver": user.token_version}
    )
    user.is_active = False
    db_session.commit()

    assert authenticate_user(
        db_session, user.username, "Acceptance-Only-Password!"
    ) is None
    assert get_current_api_user(
        request=_request(), credentials=_credentials(token), db=db_session
    ) is None
    with pytest.raises(HTTPException) as exc:
        require_api_auth(None)
    assert exc.value.status_code == 401


def test_server_session_signatures_enforce_expiry():
    signer = TimestampSigner("acceptance-session-secret")
    cookie = signer.sign(b"user-session")

    with pytest.raises(SignatureExpired):
        signer.unsign(cookie, max_age=-1)


def test_otp_request_throttle_and_attempt_lockout(
    db_session, acceptance_data, monkeypatch
):
    user = acceptance_data["users"]["l1"]
    monkeypatch.setattr("app.services.auth.send_email_via_db_smtp", lambda **_: True)
    for _ in range(3):
        assert generate_and_send_user_otp(db_session, user.email)["success"] is True
    throttled = generate_and_send_user_otp(db_session, user.email)
    assert throttled["success"] is False
    assert "Too many OTP requests" in throttled["error"]

    db_session.query(UserOTP).delete()
    record = UserOTP(
        user_id=user.id,
        email=user.email,
        otp_code=hash_password("123456"),
        expires_at=__import__("datetime").datetime.utcnow() + timedelta(minutes=10),
        is_used=False,
    )
    db_session.add(record)
    db_session.commit()
    for _ in range(5):
        assert verify_user_otp(db_session, user.email, "999999") is None
    db_session.refresh(record)
    assert record.failed_attempts == 5
    assert record.is_used is True
    assert verify_user_otp(db_session, user.email, "123456") is None
