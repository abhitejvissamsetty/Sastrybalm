from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_required_production_runbooks_are_present_and_actionable():
    required = {
        "docs/DEPLOYMENT_RUNBOOK.md": [
            "Preflight", "Deploy", "Post-deploy", "health/ready",
        ],
        "docs/ROLLBACK_RUNBOOK.md": [
            "Application-only rollback", "Schema or data rollback", "clean database",
        ],
        "docs/INCIDENT_RESPONSE_RUNBOOK.md": [
            "SEV-1", "First 15 minutes", "Closure", "Preserve",
        ],
        "docs/CREDENTIAL_ROTATION_RUNBOOK.md": [
            "Rotation order", "Webhook", "Database", "JWT", "S3",
        ],
        "docs/DISASTER_RECOVERY_DRILL_2026-07-29.md": [
            "restore", "clean",
        ],
        "docs/PARQUET_RECOVERY_DRILL_2026-07-29.md": [
            "manifest", "checksum", "restore",
        ],
    }
    failures = []
    for relative_path, phrases in required.items():
        path = ROOT / relative_path
        if not path.is_file():
            failures.append(f"{relative_path}: missing")
            continue
        text = path.read_text().lower()
        for phrase in phrases:
            if phrase.lower() not in text:
                failures.append(f"{relative_path}: missing '{phrase}'")
    assert failures == []
