from pathlib import Path

import yaml


def test_release_alert_rules_cover_required_failure_modes():
    document = yaml.safe_load(
        (Path(__file__).parents[1] / "monitoring" / "alerts.yml").read_text()
    )
    alerts = {
        rule["alert"]
        for group in document["groups"]
        for rule in group["rules"]
    }
    assert {
        "SafarHighErrorRate",
        "SafarHighP95Latency",
        "SafarReadinessFailed",
        "SafarSchedulerMissing",
        "SafarDatabasePoolSaturation",
        "SafarProcessMemoryHigh",
    } <= alerts
    for group in document["groups"]:
        for rule in group["rules"]:
            assert rule["for"]
            assert rule["labels"]["severity"] in {"warning", "critical"}
