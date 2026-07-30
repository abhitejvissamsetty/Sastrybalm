import sys
import os
import subprocess
import asyncio
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from app.services import parquet_backup_service
from app.utils import s3_service
from app.utils import backup_service
from app.config import settings
from app.routers import backup as backup_router


def test_parquet_upload_failure_never_archives_or_purges(monkeypatch):
    monkeypatch.setattr(
        parquet_backup_service,
        "get_s3_config",
        lambda db: {
            "s3_is_enabled": True,
            "s3_endpoint_url": "https://storage.example.test",
            "s3_bucket_name": "private-backups",
            "s3_access_key_id": "test-access-key",
            "s3_secret_access_key": "test-secret-key",
            "s3_region_name": "test-region",
        },
    )
    monkeypatch.setattr(
        s3_service,
        "test_s3_connection",
        lambda config, bucket_type: (True, "ok"),
    )
    monkeypatch.setattr(
        parquet_backup_service,
        "export_table_to_parquet_bytes",
        lambda db, model, cutoff: (b"parquet-data", 1),
    )

    archive = Mock()
    purge = Mock()
    monkeypatch.setattr(
        parquet_backup_service, "soft_archive_backed_up_records", archive
    )
    monkeypatch.setattr(
        parquet_backup_service, "run_hard_purge_expired_records", purge
    )

    class FailingClient:
        def put_object(self, **kwargs):
            raise RuntimeError("simulated storage outage")

    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: FailingClient()),
    )

    with pytest.raises(RuntimeError, match="no records were archived"):
        parquet_backup_service.run_daily_parquet_rolling_backup(Mock())

    archive.assert_not_called()
    purge.assert_not_called()


def test_production_upload_never_falls_back_to_local_disk(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(
        s3_service,
        "get_s3_config",
        lambda db: {"s3_is_enabled": False, "s3_files_is_enabled": False},
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError, match="local upload fallback is disabled"):
        s3_service.upload_image_file(
            Mock(), b"image", "evidence.jpg", folder_prefix="evidence"
        )

    assert not (tmp_path / "app" / "static" / "uploads").exists()


def test_sql_backup_cipher_is_independent_and_rejects_wrong_key(monkeypatch):
    monkeypatch.setattr(
        settings, "backup_encryption_key", "test-backup-key-one-with-32-characters"
    )
    encrypted = backup_service._backup_cipher().encrypt(b"CREATE TABLE evidence (id INT);")
    assert b"CREATE TABLE" not in encrypted
    assert (
        backup_service._backup_cipher().decrypt(encrypted)
        == b"CREATE TABLE evidence (id INT);"
    )

    monkeypatch.setattr(
        settings, "backup_encryption_key", "different-backup-key-with-32-characters"
    )
    with pytest.raises(Exception):
        backup_service._backup_cipher().decrypt(encrypted)


def test_encrypted_sql_backup_upload_is_private_and_integrity_checked(
    monkeypatch, tmp_path
):
    payload = b"encrypted-backup-payload"
    backup_file = tmp_path / "safar_sfa_backup_test.sql.enc"
    backup_file.write_bytes(payload)
    calls = {}

    class RecordingClient:
        def put_object(self, **kwargs):
            calls.update(kwargs)

        def head_object(self, **kwargs):
            return {
                "ContentLength": len(payload),
                "Metadata": calls["Metadata"],
            }

    monkeypatch.setattr(settings, "environment", "production")
    monkeypatch.setattr(
        s3_service,
        "get_s3_config",
        lambda db: {
            "s3_is_enabled": True,
            "s3_endpoint_url": "https://storage.example.test",
            "s3_bucket_name": "private-backups",
            "s3_access_key_id": "access-key",
            "s3_secret_access_key": "secret-key",
            "s3_region_name": "test-region",
        },
    )
    monkeypatch.setitem(
        sys.modules,
        "boto3",
        SimpleNamespace(client=lambda *args, **kwargs: RecordingClient()),
    )

    key = backup_service._upload_encrypted_backup(Mock(), str(backup_file))

    assert key == "backups/sql/safar_sfa_backup_test.sql.enc"
    assert calls["ServerSideEncryption"] == "AES256"
    assert calls["ContentType"] == "application/octet-stream"
    assert calls["Metadata"]["sha256"]


def test_encrypted_sql_restore_uses_cli_and_runs_alembic(
    monkeypatch, tmp_path
):
    monkeypatch.setattr(
        settings,
        "backup_encryption_key",
        "test-restore-key-with-at-least-32-characters",
    )
    sql = "CREATE TABLE recovery_evidence (id INT);\n"
    backup_file = tmp_path / "recovery.sql.enc"
    backup_file.write_bytes(
        backup_service._backup_cipher().encrypt(sql.encode())
    )
    restored = {}

    def fake_run(command, **kwargs):
        if command in (["psql", "--version"], ["mysql", "--version"]):
            return SimpleNamespace(returncode=0)
        restored["sql"] = Path(kwargs["stdin"].name).read_text()
        return SimpleNamespace(returncode=0, stderr="")

    upgrade = Mock()
    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr("alembic.command.upgrade", upgrade)

    backup_service.restore_sql_backup(str(backup_file))

    assert restored["sql"] == sql
    upgrade.assert_called_once()


def test_sql_backup_retention_keeps_only_five_newest(monkeypatch, tmp_path):
    monkeypatch.setattr(backup_service, "BACKUP_DIR", str(tmp_path))
    for index in range(7):
        path = tmp_path / f"safar_sfa_backup_20260101_00000{index}.sql.enc"
        path.write_bytes(b"encrypted")
        os.utime(path, (index, index))

    backup_service.cleanup_old_backups(max_retain=5)

    retained = sorted(path.name for path in tmp_path.glob("*.sql.enc"))
    assert len(retained) == 5
    assert retained[0].endswith("000002.sql.enc")


def test_admin_backup_download_serves_only_safe_encrypted_backup(
    monkeypatch, tmp_path
):
    filename = "safar_sfa_backup_20260729_142358.sql.enc"
    backup_file = tmp_path / filename
    backup_file.write_bytes(b"encrypted")
    monkeypatch.setattr(backup_router, "BACKUP_DIR", str(tmp_path))

    response = asyncio.run(
        backup_router.backup_download(filename, current_user=Mock())
    )
    assert Path(response.path) == backup_file
    assert response.media_type == "application/octet-stream"

    rejected = asyncio.run(
        backup_router.backup_download("../" + filename, current_user=Mock())
    )
    assert rejected.status_code == 302
