"""Validate external release evidence that cannot be produced by unit tests."""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse


REQUIRED_ROTATIONS = {
    "application_secret",
    "database_app",
    "database_root",
    "administrator",
    "webhook",
    "s3_permanent",
    "s3_temporary_role",
    "metrics",
    "sentry",
}
REQUIRED_UAT_ROLES = {
    "admin",
    "l4",
    "l3",
    "l2",
    "l1",
    "vendor_admin",
    "vendor_technician",
    "qc_manager",
}
REQUIRED_CI_ARTIFACTS = {
    "backend_coverage",
    "mobile_e2e",
    "security_scans",
    "migration",
    "storage",
    "backup_restore",
    "performance",
}
SHA256 = re.compile(r"^[0-9a-f]{64}$")
COMMIT = re.compile(r"^[0-9a-f]{40}$")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def require_https(value: str, field: str) -> None:
    parsed = urlparse(value)
    require(parsed.scheme == "https" and bool(parsed.netloc), f"{field} must be HTTPS")


def require_timestamp(value: str, field: str) -> None:
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    require(parsed.tzinfo is not None, f"{field} must include a timezone")
    require(parsed <= datetime.now(timezone.utc), f"{field} cannot be in the future")


def validate(data: dict) -> None:
    require(data.get("schema_version") == 1, "schema_version must equal 1")
    require(COMMIT.fullmatch(data.get("release_commit", "")) is not None, "invalid release_commit")

    rotations = data.get("credential_rotations", [])
    systems = {item.get("system") for item in rotations}
    require(systems == REQUIRED_ROTATIONS, "credential rotation set is incomplete or has unknown systems")
    for item in rotations:
        require_timestamp(item.get("rotated_at", ""), f"{item.get('system')}.rotated_at")
        require(bool(item.get("owner")), f"{item.get('system')}.owner is required")
        require(bool(item.get("evidence_id")), f"{item.get('system')}.evidence_id is required")
        require(item.get("old_credential_revoked") is True, f"{item.get('system')} old credential not revoked")
        require(item.get("post_rotation_test") is True, f"{item.get('system')} post-rotation test failed")

    webhook = data.get("webhook_rotation", {})
    require(webhook.get("sender_updated") is True, "webhook sender was not updated")
    require(webhook.get("receiver_updated") is True, "webhook receiver was not updated")
    require(webhook.get("replay_test_passed") is True, "webhook replay test did not pass")
    require(bool(webhook.get("change_id")), "webhook change_id is required")

    s3 = data.get("s3_verification", {})
    require(s3.get("passed") is True, "live S3 verification did not pass")
    require(SHA256.fullmatch(s3.get("report_sha256", "")) is not None, "invalid S3 report hash")

    observability = data.get("observability", {})
    for field in ("sentry_event_url", "sentry_trace_url", "metrics_evidence_url"):
        require_https(observability.get(field, ""), field)
    require(bool(observability.get("primary_alert_ack_id")), "primary alert acknowledgment missing")
    require(bool(observability.get("secondary_alert_ack_id")), "secondary alert acknowledgment missing")
    require(
        observability.get("redaction_verified") is True,
        "Sentry event/trace redaction was not verified",
    )

    ci = data.get("hosted_ci", {})
    require(ci.get("conclusion") == "success", "hosted CI conclusion is not success")
    require(ci.get("commit") == data["release_commit"], "hosted CI commit differs from release_commit")
    require_https(ci.get("run_url", ""), "hosted_ci.run_url")
    require(set(ci.get("artifacts", [])) == REQUIRED_CI_ARTIFACTS, "hosted CI artifact set is incomplete")

    uat = data.get("uat", [])
    roles = {item.get("role") for item in uat}
    require(roles == REQUIRED_UAT_ROLES, "UAT role set is incomplete or has unknown roles")
    for item in uat:
        require(item.get("passed") is True, f"{item.get('role')} UAT did not pass")
        require(bool(item.get("signer")), f"{item.get('role')} signer is required")
        require_timestamp(item.get("signed_at", ""), f"{item.get('role')}.signed_at")
        require(bool(item.get("evidence_id")), f"{item.get('role')} evidence_id is required")

    review = data.get("independent_security_review", {})
    require(review.get("independent") is True, "security reviewer is not independent")
    require(bool(review.get("reviewer")), "security reviewer identity is required")
    require(review.get("critical_open") == 0, "critical security findings remain open")
    require(review.get("high_open") == 0, "high security findings remain open")
    require(SHA256.fullmatch(review.get("report_sha256", "")) is not None, "invalid security report hash")
    require_timestamp(review.get("signed_at", ""), "independent_security_review.signed_at")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("evidence", type=Path)
    args = parser.parse_args()
    data = json.loads(args.evidence.read_text(encoding="utf-8"))
    validate(data)
    print("All external release evidence gates passed.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"External release evidence failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
