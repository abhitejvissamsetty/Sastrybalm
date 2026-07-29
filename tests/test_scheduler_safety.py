from datetime import datetime

import pytest
from sqlalchemy.orm import sessionmaker

from app.models.scheduler_state import SchedulerJobRun
from app.scheduler import run_guarded_job


def test_guarded_job_executes_only_once_per_bucket(db_session, monkeypatch):
    factory = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr("app.scheduler.SessionLocal", factory)
    calls = []
    now = datetime(2026, 7, 29, 6, 30)

    assert run_guarded_job("test-job", 900, lambda: calls.append("run"), now=now)
    assert not run_guarded_job(
        "test-job", 900, lambda: calls.append("duplicate"), now=now
    )

    assert calls == ["run"]
    run = db_session.query(SchedulerJobRun).one()
    assert run.status == "succeeded"


def test_guarded_job_records_and_reraises_failure(db_session, monkeypatch):
    factory = sessionmaker(bind=db_session.get_bind())
    monkeypatch.setattr("app.scheduler.SessionLocal", factory)

    def fail():
        raise ValueError("expected scheduler failure")

    with pytest.raises(ValueError, match="expected scheduler failure"):
        run_guarded_job(
            "failing-job",
            900,
            fail,
            now=datetime(2026, 7, 29, 6, 30),
        )

    run = db_session.query(SchedulerJobRun).one()
    assert run.status == "failed"
    assert "expected scheduler failure" in run.error
