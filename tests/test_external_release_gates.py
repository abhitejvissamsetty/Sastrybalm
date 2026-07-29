from datetime import datetime, timezone
from io import BytesIO

import pytest
from botocore.exceptions import ClientError

from scripts.verify_external_release_evidence import (
    REQUIRED_CI_ARTIFACTS,
    REQUIRED_ROTATIONS,
    REQUIRED_UAT_ROLES,
    validate,
)
from scripts.verify_live_s3 import assert_isolation, assert_round_trip


class FakeS3:
    def __init__(self):
        self.objects = {}
        self.deleted = []

    def put_object(self, Bucket, Key, Body, **kwargs):
        self.objects[(Bucket, Key)] = Body

    def get_object(self, Bucket, Key):
        return {"Body": BytesIO(self.objects[(Bucket, Key)])}

    def generate_presigned_url(self, *_args, **_kwargs):
        return "https://storage.example.test/signed"

    def delete_object(self, Bucket, Key):
        self.objects.pop((Bucket, Key), None)
        self.deleted.append((Bucket, Key))

    def head_object(self, Bucket, Key):
        if (Bucket, Key) not in self.objects:
            raise ClientError(
                {
                    "Error": {"Code": "404", "Message": "Not Found"},
                    "ResponseMetadata": {"HTTPStatusCode": 404},
                },
                "HeadObject",
            )


def test_live_s3_round_trip_checks_expiry_and_deletion(monkeypatch):
    payload = b"release-gate"
    s3 = FakeS3()

    class Response:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return False

        def read(self):
            return payload

    request_count = 0

    def fake_urlopen(*_args, **_kwargs):
        nonlocal request_count
        request_count += 1
        if request_count == 1:
            return Response()
        from urllib.error import HTTPError

        raise HTTPError("url", 403, "expired", {}, None)

    monkeypatch.setattr("scripts.verify_live_s3.urllib.request.urlopen", fake_urlopen)
    monkeypatch.setattr("scripts.verify_live_s3.time.sleep", lambda _seconds: None)

    result = assert_round_trip(
        s3,
        "bucket",
        "release-verification/run/object",
        payload,
        verify_expiry=True,
    )

    assert all(result.values())
    assert s3.deleted == [("bucket", "release-verification/run/object")]


def test_live_s3_isolation_rejects_readable_object():
    class Unauthorized:
        def get_object(self, **_kwargs):
            return {"Body": BytesIO(b"leak")}

    with pytest.raises(RuntimeError, match="unauthorized"):
        assert_isolation(Unauthorized(), "bucket", "key")


def complete_evidence():
    now = datetime.now(timezone.utc).isoformat()
    release_commit = "a" * 40
    return {
        "schema_version": 1,
        "release_commit": release_commit,
        "credential_rotations": [
            {
                "system": system,
                "rotated_at": now,
                "owner": "owner",
                "evidence_id": f"change-{system}",
                "old_credential_revoked": True,
                "post_rotation_test": True,
            }
            for system in REQUIRED_ROTATIONS
        ],
        "webhook_rotation": {
            "sender_updated": True,
            "receiver_updated": True,
            "replay_test_passed": True,
            "change_id": "change-webhook",
        },
        "s3_verification": {"passed": True, "report_sha256": "b" * 64},
        "observability": {
            "sentry_event_url": "https://sentry.example.test/event/1",
            "sentry_trace_url": "https://sentry.example.test/trace/1",
            "metrics_evidence_url": "https://monitoring.example.test/graph/1",
            "primary_alert_ack_id": "incident-primary",
            "secondary_alert_ack_id": "incident-secondary",
            "redaction_verified": True,
        },
        "hosted_ci": {
            "conclusion": "success",
            "commit": release_commit,
            "run_url": "https://github.com/example/repo/actions/runs/1",
            "artifacts": sorted(REQUIRED_CI_ARTIFACTS),
        },
        "uat": [
            {
                "role": role,
                "passed": True,
                "signer": f"{role}-owner",
                "signed_at": now,
                "evidence_id": f"uat-{role}",
            }
            for role in REQUIRED_UAT_ROLES
        ],
        "independent_security_review": {
            "independent": True,
            "reviewer": "external-reviewer",
            "critical_open": 0,
            "high_open": 0,
            "report_sha256": "c" * 64,
            "signed_at": now,
        },
    }


def test_external_evidence_requires_every_release_gate():
    evidence = complete_evidence()
    validate(evidence)

    evidence["uat"][0]["passed"] = False
    with pytest.raises(ValueError, match="UAT did not pass"):
        validate(evidence)
