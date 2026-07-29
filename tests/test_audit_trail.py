import json

from app.models.audit import AuditEvent
from app.services.audit import build_audit_data


def test_audit_data_classifies_and_redacts_sensitive_request_data():
    event = build_audit_data(
        method="POST",
        route="/approvals/orders/{order_id}/approve",
        status_code=200,
        actor_user_id=42,
        actor_role="territory_manager",
        client_ip="203.0.113.9",
        request_id="req-123",
        path_params={"order_id": 77},
    )

    assert event.action == "approval"
    assert event.object_type == "order"
    assert event.object_id == "77"
    assert event.outcome == "success"
    assert event.actor_hash != "42"
    assert event.ip_hash != "203.0.113.9"
    assert json.loads(event.metadata_json) == {}
    serialized = json.dumps(event.__dict__)
    assert "203.0.113.9" not in serialized
    assert "password" not in serialized
    assert "token" not in serialized


def test_audit_event_persists_in_isolated_database(db_session):
    data = build_audit_data(
        method="GET",
        route="/operations/orders/{order_id}",
        status_code=403,
        request_id="req-denied",
        path_params={"order_id": 12},
    )
    db_session.add(AuditEvent(**data.__dict__))
    db_session.commit()

    stored = db_session.query(AuditEvent).one()
    assert stored.action == "read"
    assert stored.outcome == "denied"
    assert stored.object_id == "12"
    assert stored.request_id == "req-denied"
