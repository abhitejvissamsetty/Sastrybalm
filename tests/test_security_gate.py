import asyncio

import pytest

from app.config import Settings


def production_settings(**overrides):
    values = {
        "environment": "production",
        "secret_key": "a-unique-production-secret-that-is-long-enough",
        "db_user": "safar_app",
        "db_password": "a-rotated-database-password",
        "admin_password": "a-rotated-admin-password",
        "backup_encryption_key": "an-independent-backup-encryption-key-value",
        "smtp_host": "smtp.example",
        "smtp_user": "safar@example",
        "smtp_password": "a-rotated-smtp-password",
        "secure_cookies": True,
        "enable_api_docs": False,
        "cors_origins": "https://safar.example",
        "sentry_dsn": "https://public@example.test/1",
        "metrics_token": "a-unique-metrics-token-that-is-long-enough",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


def test_production_rejects_default_secret():
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        production_settings(secret_key="change-this-in-production").validate_runtime_security()


def test_production_accepts_explicit_security_configuration():
    production_settings().validate_runtime_security()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"smtp_host": ""}, "SMTP_HOST"),
        ({"smtp_password": ""}, "SMTP_PASSWORD"),
        ({"enable_api_docs": True}, "ENABLE_API_DOCS"),
        ({"cors_origins": "http://safar.example"}, "HTTPS"),
        ({"secure_cookies": False}, "SECURE_COOKIES"),
        ({"cors_origins": "*"}, "CORS_ORIGINS"),
        ({"cors_origins": ""}, "CORS_ORIGINS"),
    ],
)
def test_production_rejects_incomplete_security_configuration(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        production_settings(**overrides).validate_runtime_security()


@pytest.mark.parametrize(
    ("overrides", "message"),
    [
        ({"db_user": "root"}, "DB_USER"),
        ({"db_password": "safar_password"}, "DB_PASSWORD"),
        ({"db_password": "too-short"}, "DB_PASSWORD"),
        ({"admin_password": "admin123"}, "ADMIN_PASSWORD"),
        ({"admin_password": "too-short"}, "ADMIN_PASSWORD"),
        ({"smtp_password": "too-short"}, "SMTP_PASSWORD"),
    ],
)
def test_production_rejects_default_or_weak_credentials(overrides, message):
    with pytest.raises(RuntimeError, match=message):
        production_settings(**overrides).validate_runtime_security()


def test_retired_integration_routes_are_absent():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/v1/webhooks/cmms" not in paths
    assert not any("sync-cmms" in path for path in paths)
    assert not any("sync-connect" in path for path in paths)
    assert not any("test-zap" in path for path in paths)


def test_outbound_webhook_signature_binds_timestamp_and_payload():
    from app.routers.settings import build_webhook_signature

    secret = "a-strong-webhook-secret-with-32-characters"
    signature = build_webhook_signature(secret, b'{"event":"order.created"}', "1000")
    assert signature.startswith("sha256=")
    assert signature != build_webhook_signature(
        secret, b'{"event":"order.updated"}', "1000"
    )
    assert signature != build_webhook_signature(
        secret, b'{"event":"order.created"}', "1001"
    )


def test_debug_login_route_is_removed():
    from app.main import app

    paths = set(app.openapi()["paths"])
    assert "/api/auth/login" not in paths
    assert "/api/v1/auth/token" in paths


def test_otp_response_contract_never_contains_code(monkeypatch):
    from app.routers.api.auth import api_request_otp
    from app.schemas.auth import RequestOtpSchema

    monkeypatch.setattr(
        "app.routers.api.auth.generate_and_send_user_otp",
        lambda db, email: {
            "success": True,
            "message": "OTP verification code sent.",
            "email": email,
            "email_sent": True,
        },
    )
    response = asyncio.run(
        api_request_otp(RequestOtpSchema(email="user@example.com"), object())
    )
    assert "otp_code" not in response
