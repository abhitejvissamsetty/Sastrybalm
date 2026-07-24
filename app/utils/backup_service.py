"""
Backup Service — Generates full system database backups in JSON and ZIP formats.
Supports instant web download and automated daily scheduler backups.
"""
import os
import json
import zipfile
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy.orm import Session
from app.database import SessionLocal, engine
from app.models.base import Base

BACKUP_DIR = "/app/app/static/uploads/backups"


def _json_serializer(obj: Any) -> Any:
    if isinstance(obj, (datetime, datetime.date)):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    if hasattr(obj, "value"):  # Handle Enums
        return obj.value
    raise TypeError(f"Type {type(obj)} not serializable")


def create_full_system_backup() -> str:
    """Export all database tables into JSON files and bundle them into a timestamped ZIP archive."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_filename = f"sastrybalm_sfa_backup_{timestamp}.zip"
    zip_filepath = os.path.join(BACKUP_DIR, zip_filename)

    db: Session = SessionLocal()
    backup_data: Dict[str, Any] = {
        "metadata": {
            "exported_at": datetime.now().isoformat(),
            "version": "Sastrybalm SFA v2.0 Enterprise",
            "db_engine": str(engine.url),
        },
        "tables": {}
    }

    try:
        # Reflect all mapped tables from Base metadata
        for table_name in Base.metadata.tables.keys():
            try:
                result = db.execute(f"SELECT * FROM `{table_name}`").fetchall()
                keys = db.execute(f"SELECT * FROM `{table_name}` LIMIT 1").keys() if result else []
                rows = [dict(zip(keys, row)) for row in result]
                backup_data["tables"][table_name] = rows
            except Exception as e:
                backup_data["tables"][table_name] = {"error": str(e)}

        # Write to temporary json file and zip
        json_filename = f"sastrybalm_export_{timestamp}.json"
        json_filepath = os.path.join(BACKUP_DIR, json_filename)

        with open(json_filepath, "w", encoding="utf-8") as f:
            json.dump(backup_data, f, default=_json_serializer, indent=2)

        with zipfile.ZipFile(zip_filepath, "w", zipfile.ZIP_DEFLATED) as zipf:
            zipf.write(json_filepath, arcname=json_filename)

        # Cleanup uncompressed json
        if os.path.exists(json_filepath):
            os.remove(json_filepath)

        return zip_filepath

    finally:
        db.close()


def list_existing_backups() -> list:
    """Return list of existing backup zip files with size and timestamp metadata."""
    os.makedirs(BACKUP_DIR, exist_ok=True)
    files = []
    for fname in os.listdir(BACKUP_DIR):
        if fname.endswith(".zip") and fname.startswith("sastrybalm_sfa_backup_"):
            fpath = os.path.join(BACKUP_DIR, fname)
            stat = os.stat(fpath)
            files.append({
                "filename": fname,
                "filepath": fpath,
                "size_mb": round(stat.st_size / (1024 * 1024), 2),
                "created_at": datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S"),
            })
    files.sort(key=lambda x: x["filename"], reverse=True)
    return files
