"""
Backup Service — Generates full system database backups in standard executable SQL (.sql) format.
Supports instant web download, automatic 5-backup retention policy (deletes older backups),
and automated daily scheduler backups.
"""
from __future__ import annotations

import os
import re
import logging
import base64
import hashlib
import tempfile
from datetime import datetime, date
from decimal import Decimal
from typing import Any, List
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from app.database import SessionLocal
from cryptography.fernet import Fernet, InvalidToken

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.getenv("BACKUP_DIR", os.path.join(os.path.dirname(BASE_DIR), "var", "backups"))
MAX_BACKUP_RETENTION = 5

logger = logging.getLogger(__name__)


def _backup_cipher() -> Fernet:
    from app.config import settings

    if not settings.backup_encryption_key:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is required for SQL backup operations.")
    key = hashlib.sha256(settings.backup_encryption_key.encode()).digest()
    return Fernet(base64.urlsafe_b64encode(key))


def _upload_encrypted_backup(db: Session, filepath: str) -> str | None:
    """Upload and verify an encrypted SQL backup in the private permanent bucket."""
    from app.config import settings
    from app.utils.s3_service import get_s3_config

    config = get_s3_config(db)
    required = (
        config.get("s3_is_enabled"),
        config.get("s3_bucket_name"),
        config.get("s3_access_key_id"),
        config.get("s3_secret_access_key"),
    )
    if not all(required):
        if settings.is_production:
            raise RuntimeError(
                "Permanent object storage is required for production SQL backups."
            )
        return None

    import boto3

    with open(filepath, "rb") as backup_file:
        payload = backup_file.read()
    digest = hashlib.sha256(payload).hexdigest()
    object_key = f"backups/sql/{os.path.basename(filepath)}"
    client = boto3.client(
        "s3",
        endpoint_url=config.get("s3_endpoint_url") or None,
        aws_access_key_id=config["s3_access_key_id"],
        aws_secret_access_key=config["s3_secret_access_key"],
        region_name=config.get("s3_region_name") or "us-east-1",
    )
    client.put_object(
        Bucket=config["s3_bucket_name"],
        Key=object_key,
        Body=payload,
        ContentType="application/octet-stream",
        ServerSideEncryption="AES256",
        Metadata={"sha256": digest},
    )
    stored = client.head_object(Bucket=config["s3_bucket_name"], Key=object_key)
    if (
        stored.get("ContentLength") != len(payload)
        or stored.get("Metadata", {}).get("sha256") != digest
    ):
        raise RuntimeError("Remote SQL backup integrity verification failed.")
    return object_key


def _sql_escape_value(val: Any, is_postgres: bool = False) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        if is_postgres:
            return "TRUE" if val else "FALSE"
        return "1" if val else "0"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, (datetime, date)):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(val, (dict, list)):
        import json
        s = json.dumps(val)
        escaped = s.replace("\\", "\\\\").replace("'", "''" if is_postgres else "\\'").replace("\0", "")
        return f"'{escaped}'"
    if hasattr(val, "value"):  # Enums
        s = str(val.value)
    else:
        s = str(val)
    if is_postgres:
        escaped = s.replace("'", "''")
    else:
        escaped = s.replace("\\", "\\\\").replace("'", "\\'").replace("\0", "\\0").replace("\n", "\\n").replace("\r", "\\r")
    return f"'{escaped}'"


def cleanup_old_backups(max_retain: int = MAX_BACKUP_RETENTION) -> None:
    """Retain only the most recent `max_retain` backup files, removing older ones."""
    if not os.path.exists(BACKUP_DIR):
        return
    backup_files = []
    for fname in os.listdir(BACKUP_DIR):
        if fname.endswith(".sql.enc") and fname.startswith("safar_sfa_backup_"):
            fpath = os.path.join(BACKUP_DIR, fname)
            stat = os.stat(fpath)
            backup_files.append((fpath, stat.st_mtime))

    backup_files.sort(key=lambda x: x[1], reverse=True)

    if len(backup_files) > max_retain:
        for fpath, _ in backup_files[max_retain:]:
            try:
                os.remove(fpath)
                logger.info("Purged old backup file exceeding retention limit: %s", fpath)
            except Exception as e:
                logger.error("Failed to purge old backup file %s: %s", fpath, e)


def create_full_system_backup() -> str:
    """Export all database tables into a clean, executable timestamped .sql file and retain the last 5 backups."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    sql_filename = f"safar_sfa_backup_{timestamp}.sql.enc"
    sql_filepath = os.path.join(BACKUP_DIR, sql_filename)

    db: Session = SessionLocal()
    is_postgres = (db.bind.dialect.name == "postgresql") if db.bind else False
    def q(identifier: str) -> str:
        return f'"{identifier}"' if is_postgres else f'`{identifier}`'

    engine_name = "PostgreSQL" if is_postgres else "MySQL / MariaDB"
    sql_lines: List[str] = [
        "-- ========================================================",
        "-- Safar SFA Enterprise SQL Database Backup",
        f"-- Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"-- Database Engine: {engine_name}",
        "-- Software Version: Safar SFA v2.0 Enterprise",
        "-- ========================================================\n",
    ]

    if is_postgres:
        sql_lines.append("SET session_replication_role = 'replica';\n")
    else:
        sql_lines.append("SET FOREIGN_KEY_CHECKS=0;")
        sql_lines.append("SET SQL_MODE = \"NO_AUTO_VALUE_ON_ZERO\";")
        sql_lines.append("SET time_zone = \"+00:00\";\n")

    try:
        table_names = inspect(db.get_bind()).get_table_names()
        if "alembic_version" not in table_names:
            raise RuntimeError(
                "Database is not Alembic-managed; refusing an unrecoverable SQL backup."
            )
        for table_name in table_names:
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"-- Table structure for table {q(table_name)}")
            sql_lines.append(f"-- --------------------------------------------------------")
            if is_postgres:
                sql_lines.append(f"DROP TABLE IF EXISTS {q(table_name)} CASCADE;\n")
            else:
                sql_lines.append(f"DROP TABLE IF EXISTS `{table_name}`;")
                create_res = db.execute(text(f"SHOW CREATE TABLE `{table_name}`")).fetchone()
                if not create_res or len(create_res) < 2:
                    raise RuntimeError(f"Unable to read schema for backup table {table_name}.")
                sql_lines.append(f"{create_res[1]};\n")

            result = db.execute(text(f"SELECT * FROM {q(table_name)}"))
            keys = list(result.keys())
            rows = result.fetchall()
            if rows:
                col_names = ", ".join([q(col) for col in keys])
                sql_lines.append(f"-- Dumping data for table {q(table_name)}")

                value_rows = []
                for row in rows:
                    row_dict = dict(zip(keys, row))
                    val_str = ", ".join([_sql_escape_value(row_dict[col], is_postgres) for col in keys])
                    value_rows.append(f"({val_str})")

                batch_size = 100
                for i in range(0, len(value_rows), batch_size):
                    batch = value_rows[i:i + batch_size]
                    sql_lines.append(f"INSERT INTO {q(table_name)} ({col_names}) VALUES\n" + ",\n".join(batch) + ";")
                sql_lines.append("")

        if is_postgres:
            sql_lines.append("SET session_replication_role = 'origin';\n")
        else:
            sql_lines.append("SET FOREIGN_KEY_CHECKS=1;\n")

        encrypted = _backup_cipher().encrypt("\n".join(sql_lines).encode("utf-8"))
        with open(sql_filepath, "wb") as f:
            f.write(encrypted)
        os.chmod(sql_filepath, 0o600)
        _upload_encrypted_backup(db, sql_filepath)

        # Enforce maximum 5 backups retention policy
        cleanup_old_backups(max_retain=MAX_BACKUP_RETENTION)

        return sql_filepath

    finally:
        db.close()


def list_existing_backups() -> list:
    """Return list of existing backup .sql files with size and timestamp metadata."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = []
    for fname in os.listdir(BACKUP_DIR):
        if fname.endswith(".sql.enc") and fname.startswith("safar_sfa_backup_"):
            fpath = os.path.join(BACKUP_DIR, fname)
            stat = os.stat(fpath)
            size_mb = round(stat.st_size / (1024 * 1024), 2)
            if size_mb == 0.0:
                size_str = f"{round(stat.st_size / 1024, 2)} KB"
            else:
                size_str = f"{size_mb} MB"

            files.append({
                "filename": fname,
                "filepath": fpath,
                "size_mb": size_mb,
                "size_display": size_str,
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    files.sort(key=lambda x: x["filename"], reverse=True)
    return files


def restore_sql_backup(sql_filepath: str, db: Session = None) -> None:
    """Restore an encrypted SQL backup and require Alembic convergence."""
    if not os.path.exists(sql_filepath):
        raise FileNotFoundError(f"Backup file not found at '{sql_filepath}'")

    import subprocess
    from app.config import settings
    try:
        with open(sql_filepath, "rb") as encrypted_file:
            sql_content = _backup_cipher().decrypt(encrypted_file.read()).decode("utf-8")
    except InvalidToken as exc:
        raise RuntimeError("Backup decryption failed; key or file is invalid.") from exc

    # Fast path: pipe via psql or mysql CLI subprocess if available
    cli_cmd = None
    cli_env = os.environ.copy()
    try:
        check_pg = subprocess.run(["psql", "--version"], capture_output=True, timeout=5)
        if check_pg.returncode == 0:
            cli_cmd = [
                "psql",
                "-h", settings.db_host,
                "-p", str(settings.db_port),
                "-U", settings.db_user,
                "-d", settings.db_name,
            ]
            cli_env["PGPASSWORD"] = settings.db_password
    except Exception:
        pass

    if cli_cmd is None:
        try:
            check_mysql = subprocess.run(["mysql", "--version"], capture_output=True, timeout=5)
            if check_mysql.returncode == 0:
                cli_cmd = [
                    "mysql",
                    f"-h{settings.db_host}",
                    f"-P{settings.db_port}",
                    f"-u{settings.db_user}",
                    f"-p{settings.db_password}",
                    settings.db_name,
                ]
        except Exception:
            pass

    if cli_cmd:
        try:
            with tempfile.NamedTemporaryFile(
                mode="w", encoding="utf-8", suffix=".sql"
            ) as f:
                os.chmod(f.name, 0o600)
                f.write(sql_content)
                f.flush()
                f.seek(0)
                result = subprocess.run(
                    cli_cmd,
                    stdin=f,
                    capture_output=True,
                    text=True,
                    timeout=120,
                    env=cli_env,
                )
            if result.returncode != 0:
                raise RuntimeError(f"CLI restore failed: {result.stderr[:500]}")
            else:
                logger.info("CLI restore succeeded: %s", sql_filepath)
                from alembic import command
                from alembic.config import Config
                command.upgrade(Config("alembic.ini"), "head")
                return
        except Exception as e:
            raise RuntimeError("SQL backup restore failed.") from e

    # Fallback: statement-by-statement via SQLAlchemy using passed session or new one
    close_db = False
    if db is None:
        db = SessionLocal()
        close_db = True

    try:
        # Normalize line endings and split on semicolons
        sql_content = sql_content.replace("\r\n", "\n")
        raw_stmts = re.split(r";\s*\n", sql_content)

        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET session_replication_role = 'replica';"))
        else:
            db.execute(text("SET FOREIGN_KEY_CHECKS=0;"))

        for raw in raw_stmts:
            stmt = raw.strip()
            if not stmt:
                continue
            # Skip pure comment blocks and MySQL directives
            lines = [l for l in stmt.splitlines()
                     if l.strip() and not l.strip().startswith("--") and not l.strip().startswith("/*")]
            if not lines:
                continue
            clean = "\n".join(lines)
            if clean.startswith("/*!"):
                continue
            # Skip LOCK/UNLOCK statements — not needed for restore
            if clean.upper().startswith("LOCK TABLES") or clean.upper().startswith("UNLOCK TABLES"):
                continue
            db.execute(text(clean))

        if db.bind and db.bind.dialect.name == "postgresql":
            db.execute(text("SET session_replication_role = 'origin';"))
        else:
            db.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
        db.commit()
        logger.info("SQLAlchemy restore completed: %s", sql_filepath)
    except Exception as e:
        db.rollback()
        logger.error("Error restoring database backup: %s", e)
        raise
    finally:
        if close_db:
            db.close()

    from alembic import command
    from alembic.config import Config
    command.upgrade(Config("alembic.ini"), "head")
