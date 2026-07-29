"""Fail CI when the effective production Compose file exposes private services."""

import json
import os
import subprocess
import sys


SAFE_EXAMPLE_ENV = {
    "MYSQL_ROOT_PASSWORD": "Root-Example-Only-2026!",
    "DB_NAME": "safar_prod",
    "DB_USER": "safar_app",
    "DB_PASSWORD": "Database-Example-Only-2026!",
    "SECRET_KEY": "Example-Only-Secret-Key-At-Least-32-Characters!",
    "ADMIN_PASSWORD": "Admin-Example-Only-2026!",
    "BACKUP_ENCRYPTION_KEY": "Backup-Encryption-Example-Only-2026-Key!",
    "SMTP_HOST": "smtp.example.test",
    "SMTP_PASSWORD": "SMTP-Example-Only-2026-Password!",
    "SMTP_FROM": "noreply@example.test",
    "CORS_ORIGINS": "https://sfa.example.invalid",
    "METRICS_TOKEN": "Metrics-Example-Only-Token-2026-Long!",
    "SENTRY_DSN": "https://public@example.invalid/1",
    "TLS_CERT_DIR": "/private/tmp/safar-test-certs",
}


def verify(config: dict) -> None:
    services = config["services"]
    for name in ("db", "app"):
        if services[name].get("ports"):
            raise RuntimeError(f"Production service {name} publishes host ports")

    if "adminer" in services:
        if services["adminer"].get("ports"):
            raise RuntimeError("Production Adminer publishes a host port")
        profiles = set(services["adminer"].get("profiles", []))
        if "diagnostics" not in profiles:
            raise RuntimeError("Production Adminer is not disabled behind diagnostics profile")

    nginx_ports = {
        int(port["target"])
        for port in services["nginx"].get("ports", [])
    }
    if nginx_ports != {80, 443}:
        raise RuntimeError(
            f"Production Nginx must publish only ports 80 and 443; got {nginx_ports}"
        )

    app_env = services["app"]["environment"]
    required = {
        "ENVIRONMENT": "production",
        "SECURE_COOKIES": "true",
        "ENABLE_API_DOCS": "false",
    }
    for key, expected in required.items():
        if str(app_env.get(key)).lower() != expected:
            raise RuntimeError(f"Production {key} must equal {expected}")

    for name in ("app", "scheduler"):
        for volume in services[name].get("volumes", []):
            if volume.get("type") == "bind" and volume.get("target", "").startswith("/app/app"):
                raise RuntimeError(f"Production {name} bind-mounts application source")


def main() -> None:
    env = os.environ.copy()
    env.update(SAFE_EXAMPLE_ENV)
    result = subprocess.run(
        [
            "docker", "compose",
            "-f", "docker-compose.yml",
            "-f", "docker-compose.production.yml",
            "config", "--format", "json",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )
    verify(json.loads(result.stdout))
    print("Production Compose exposure and security invariants passed.")


if __name__ == "__main__":
    try:
        main()
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or str(exc)).strip()
        print(f"Production Compose verification failed: {detail}", file=sys.stderr)
        raise SystemExit(1)
    except (KeyError, RuntimeError) as exc:
        print(f"Production Compose verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
