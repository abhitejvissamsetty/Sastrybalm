import asyncio
import json

from app import main
from app.services import startup_validation


CHECK_NAMES = {
    "database",
    "migrations",
    "object_storage",
    "smtp",
    "scheduler",
}


def test_readiness_endpoint_requires_every_dependency(monkeypatch):
    healthy = {name: True for name in CHECK_NAMES}
    monkeypatch.setattr(main, "readiness_checks", lambda: healthy)
    response = asyncio.run(main.readiness())
    assert response.status_code == 200
    assert json.loads(response.body)["status"] == "ready"

    unhealthy = {**healthy, "object_storage": False}
    monkeypatch.setattr(main, "readiness_checks", lambda: unhealthy)
    response = asyncio.run(main.readiness())
    assert response.status_code == 503
    assert json.loads(response.body)["checks"]["object_storage"] is False


def test_readiness_fails_closed_when_database_is_unavailable(monkeypatch):
    class BrokenSession:
        def execute(self, *_):
            raise RuntimeError("database unavailable")

        def close(self):
            self.closed = True

    session = BrokenSession()
    monkeypatch.setattr(startup_validation, "SessionLocal", lambda: session)

    checks = startup_validation.readiness_checks()

    assert set(checks) == CHECK_NAMES
    assert not any(checks.values())
    assert session.closed is True
