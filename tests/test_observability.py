import json
import logging

import pytest
from fastapi import HTTPException
from starlette.requests import Request

from app.config import settings
from app.observability import RedactingJsonFormatter, metrics_response, redact


def _request(token=""):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/metrics",
            "headers": (
                [(b"x-metrics-token", token.encode())] if token else []
            ),
        }
    )


def _bearer_request(token=""):
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/metrics",
            "headers": [(b"authorization", f"Bearer {token}".encode())],
        }
    )


def test_structured_logging_redacts_secrets_and_pii():
    record = logging.LogRecord(
        "acceptance",
        logging.INFO,
        __file__,
        1,
        "Authorization Bearer signed.jwt.value for person@example.test",
        (),
        None,
    )
    payload = json.loads(RedactingJsonFormatter().format(record))
    assert payload["level"] == "INFO"
    assert "signed.jwt.value" not in payload["message"]
    assert "person@example.test" not in payload["message"]
    assert redact({"otp": "123456", "phone": "9999999999"}) == {
        "otp": "[REDACTED]",
        "phone": "[REDACTED]",
    }


def test_metrics_endpoint_fails_closed_and_accepts_constant_time_token(
    monkeypatch,
):
    monkeypatch.setattr(settings, "metrics_token", "metrics-token-test-value")
    with pytest.raises(HTTPException) as exc:
        metrics_response(_request("wrong"))
    assert exc.value.status_code == 404

    response = metrics_response(_request("metrics-token-test-value"))
    assert response.status_code == 200
    assert b"safar_http_requests_total" in response.body

    bearer_response = metrics_response(_bearer_request("metrics-token-test-value"))
    assert bearer_response.status_code == 200


def test_sentry_initialization_redacts_request_data_and_enables_tracing(
    monkeypatch,
):
    import sentry_sdk
    from app.observability import configure_observability

    captured = {}
    monkeypatch.setattr(settings, "sentry_dsn", "https://public@example.test/1")
    monkeypatch.setattr(settings, "sentry_traces_sample_rate", 0.25)
    monkeypatch.setattr(sentry_sdk, "init", lambda **kwargs: captured.update(kwargs))

    configure_observability()
    assert captured["send_default_pii"] is False
    assert captured["traces_sample_rate"] == 0.25
    event = captured["before_send"](
        {
            "user": {"email": "person@example.test"},
            "request": {
                "data": {"password": "secret"},
                "cookies": {"session": "secret"},
                "headers": {"Authorization": "Bearer secret"},
                "query_string": "token=secret",
            },
        },
        {},
    )
    assert "user" not in event
    assert "data" not in event["request"]
    assert "cookies" not in event["request"]
    assert event["request"]["headers"] == {}
    assert event["request"]["query_string"] == "[REDACTED]"
