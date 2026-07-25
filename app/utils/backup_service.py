"""
Backup Service — Generates full system database backups in standard executable SQL (.sql) format.
Supports instant web download, automatic 5-backup retention policy (deletes older backups),
and automated daily scheduler backups.
"""
import os
import logging
from datetime import datetime, date
from decimal import Decimal
from typing import Any, List
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.base import Base

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKUP_DIR = os.path.join(BASE_DIR, "static", "uploads", "backups")
MAX_BACKUP_RETENTION = 5

logger = logging.getLogger(__name__)


def _sql_escape_value(val: Any) -> str:
    if val is None:
        return "NULL"
    if isinstance(val, bool):
        return "1" if val else "0"
    if isinstance(val, (int, float, Decimal)):
        return str(val)
    if isinstance(val, (datetime, date)):
        return f"'{val.strftime('%Y-%m-%d %H:%M:%S')}'"
    if isinstance(val, (dict, list)):
        import json
        s = json.dumps(val)
        escaped = s.replace("\\", "\\\\").replace("'", "\\'").replace("\0", "\\0").replace("\n", "\\n").replace("\r", "\\r")
        return f"'{escaped}'"
    if hasattr(val, "value"):  # Enums
        s = str(val.value)
    else:
        s = str(val)
    escaped = s.replace("\\", "\\\\").replace("'", "\\'").replace("\0", "\\0").replace("\n", "\\n").replace("\r", "\\r")
    return f"'{escaped}'"


def cleanup_old_backups(max_retain: int = MAX_BACKUP_RETENTION) -> None:
    """Retain only the most recent `max_retain` backup files, removing older ones."""
    if not os.path.exists(BACKUP_DIR):
        return
    backup_files = []
    for fname in os.listdir(BACKUP_DIR):
        if (fname.endswith(".sql") or fname.endswith(".zip")) and fname.startswith("sastrybalm_sfa_backup_"):
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
    sql_filename = f"sastrybalm_sfa_backup_{timestamp}.sql"
    sql_filepath = os.path.join(BACKUP_DIR, sql_filename)

    db: Session = SessionLocal()
    sql_lines: List[str] = [
        "-- ========================================================",
        "-- Sastrybalm SFA Enterprise SQL Database Backup",
        f"-- Generated At: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "-- Database Engine: MySQL / MariaDB",
        "-- Software Version: Sastrybalm SFA v2.0 Enterprise",
        "-- ========================================================\n",
        "SET FOREIGN_KEY_CHECKS=0;",
        "SET SQL_MODE = \"NO_AUTO_VALUE_ON_ZERO\";",
        "SET time_zone = \"+00:00\";\n",
    ]

    try:
        table_names = list(Base.metadata.tables.keys())
        for table_name in table_names:
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"-- Table structure for table `{table_name}`")
            sql_lines.append(f"-- --------------------------------------------------------")
            sql_lines.append(f"DROP TABLE IF EXISTS `{table_name}`;")
            try:
                create_res = db.execute(text(f"SHOW CREATE TABLE `{table_name}`")).fetchone()
                if create_res and len(create_res) >= 2:
                    sql_lines.append(f"{create_res[1]};\n")
            except Exception:
                pass

            try:
                result = db.execute(text(f"SELECT * FROM `{table_name}`")).fetchall()
                if result:
                    keys = db.execute(text(f"SELECT * FROM `{table_name}` LIMIT 1")).keys()
                    col_names = ", ".join([f"`{col}`" for col in keys])
                    sql_lines.append(f"-- Dumping data for table `{table_name}`")
                    
                    value_rows = []
                    for row in result:
                        row_dict = dict(zip(keys, row))
                        val_str = ", ".join([_sql_escape_value(row_dict[col]) for col in keys])
                        value_rows.append(f"({val_str})")

                    batch_size = 100
                    for i in range(0, len(value_rows), batch_size):
                        batch = value_rows[i:i + batch_size]
                        sql_lines.append(f"INSERT INTO `{table_name}` ({col_names}) VALUES\n" + ",\n".join(batch) + ";")
                    sql_lines.append("")
            except Exception as e:
                sql_lines.append(f"-- Error dumping table `{table_name}`: {e}\n")

        sql_lines.append("SET FOREIGN_KEY_CHECKS=1;\n")

        with open(sql_filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(sql_lines))

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
        if (fname.endswith(".sql") or fname.endswith(".zip")) and fname.startswith("sastrybalm_sfa_backup_"):
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


def restore_sql_backup(sql_filepath: str) -> None:
    """Execute a .sql backup file into the MySQL database and run db_migrate.py to sync schema."""
    if not os.path.exists(sql_filepath):
        raise FileNotFoundError(f"Backup file not found at '{sql_filepath}'")

    db: Session = SessionLocal()
    try:
        db.execute(text("SET FOREIGN_KEY_CHECKS=0;"))
        with open(sql_filepath, "r", encoding="utf-8", errors="ignore") as f:
            sql_content = f.read()

        statement_buffer = []
        for line in sql_content.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith("--") or stripped.startswith("/*"):
                continue
            statement_buffer.append(line)
            if stripped.endswith(";"):
                stmt = "\n".join(statement_buffer).strip()
                if stmt:
                    try:
                        db.execute(text(stmt))
                    except Exception as e:
                        logger.warning("Error executing restore SQL statement: %s", e)
                statement_buffer = []

        db.execute(text("SET FOREIGN_KEY_CHECKS=1;"))
        db.commit()
        logger.info("Successfully executed restore script: %s", sql_filepath)
    finally:
        db.close()

    try:
        from db_migrate import run_migrations
        run_migrations()
    except Exception as e:
        logger.warning("Error running db_migrate post-restore: %s", e)
