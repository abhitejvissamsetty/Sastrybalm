import io
import hashlib
import hmac
import json
import logging
from datetime import datetime, date, timedelta, time
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from app.utils.s3_service import get_s3_config
from app.config import settings

logger = logging.getLogger(__name__)

PARQUET_PREFIX = "rolling_backups/parquet"


def _canonical_manifest_bytes(manifest: Dict[str, Any]) -> bytes:
    unsigned = {key: value for key, value in manifest.items() if key != "signature"}
    return json.dumps(
        unsigned, sort_keys=True, separators=(",", ":"), default=str
    ).encode("utf-8")


def _manifest_signature(manifest: Dict[str, Any]) -> str:
    if len(settings.backup_encryption_key) < 32:
        raise RuntimeError("BACKUP_ENCRYPTION_KEY is required to sign Parquet manifests.")
    return hmac.new(
        settings.backup_encryption_key.encode("utf-8"),
        _canonical_manifest_bytes(manifest),
        hashlib.sha256,
    ).hexdigest()


def _s3_client(config: Dict[str, Any]):
    import boto3

    endpoint_url = config.get("s3_endpoint_url")
    if endpoint_url and not endpoint_url.startswith("http"):
        endpoint_url = f"https://{endpoint_url}"
    return boto3.client(
        "s3",
        endpoint_url=endpoint_url or None,
        aws_access_key_id=config.get("s3_access_key_id"),
        aws_secret_access_key=config.get("s3_secret_access_key"),
        region_name=config.get("s3_region_name") or "us-west-004",
    )


def verify_parquet_backup(
    client, bucket: str, backup_date: date
) -> Dict[str, List[Dict[str, Any]]]:
    """Download, authenticate, checksum, and decode a complete backup set."""
    date_str = backup_date.strftime("%Y-%m-%d")
    manifest_key = f"{PARQUET_PREFIX}/{date_str}/manifest.json"
    raw_manifest = client.get_object(Bucket=bucket, Key=manifest_key)["Body"].read()
    manifest = json.loads(raw_manifest)
    supplied_signature = manifest.get("signature", "")
    expected_signature = _manifest_signature(manifest)
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise RuntimeError("Parquet backup manifest signature verification failed.")

    import pyarrow.parquet as pq

    recovered = {}
    for item in manifest["files"]:
        body = client.get_object(Bucket=bucket, Key=item["object_key"])["Body"].read()
        digest = hashlib.sha256(body).hexdigest()
        if not hmac.compare_digest(digest, item["sha256"]):
            raise RuntimeError(
                f"Parquet checksum verification failed for {item['object_key']}."
            )
        if len(body) != item["size_bytes"]:
            raise RuntimeError(
                f"Parquet size verification failed for {item['object_key']}."
            )
        table = pq.read_table(io.BytesIO(body))
        rows = table.to_pylist()
        if len(rows) != item["record_count"]:
            raise RuntimeError(
                f"Parquet row-count verification failed for {item['object_key']}."
            )
        recovered[item["table_name"]] = rows
    return recovered


def restore_verified_parquet_backup(
    db: Session,
    recovered: Dict[str, List[Dict[str, Any]]],
    model_by_table: Dict[str, Any],
) -> Dict[str, int]:
    """Restore verified rows into empty target tables in manifest/model order."""
    restored = {}
    try:
        for table_name, rows in recovered.items():
            model = model_by_table.get(table_name)
            if model is None:
                continue
            if db.query(model).limit(1).first() is not None:
                raise RuntimeError(
                    f"Restore target table {table_name} is not empty."
                )
            normalized_rows = []
            for row in rows:
                normalized = dict(row)
                for column in model.__table__.columns:
                    value = normalized.get(column.name)
                    if not isinstance(value, str):
                        continue
                    try:
                        python_type = column.type.python_type
                    except (AttributeError, NotImplementedError):
                        continue
                    if python_type is datetime:
                        normalized[column.name] = datetime.fromisoformat(value)
                    elif python_type is date:
                        normalized[column.name] = date.fromisoformat(value)
                normalized_rows.append(normalized)
            if normalized_rows:
                db.bulk_insert_mappings(model, normalized_rows)
            restored[table_name] = len(rows)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return restored


def enforce_parquet_object_retention(
    client, bucket: str, now: Optional[date] = None
) -> int:
    """Delete only complete date prefixes older than the long-term retention."""
    today = now or datetime.utcnow().date()
    cutoff = today - timedelta(days=settings.parquet_backup_retention_days)
    response = client.list_objects_v2(Bucket=bucket, Prefix=f"{PARQUET_PREFIX}/")
    keys_to_delete = []
    for item in response.get("Contents", []):
        key = item["Key"]
        parts = key.split("/")
        if len(parts) < 4:
            continue
        try:
            object_date = datetime.strptime(parts[2], "%Y-%m-%d").date()
        except ValueError:
            continue
        if object_date < cutoff:
            keys_to_delete.append({"Key": key})
    if keys_to_delete:
        client.delete_objects(Bucket=bucket, Delete={"Objects": keys_to_delete})
    return len(keys_to_delete)


def model_to_dict(obj: Any) -> Dict[str, Any]:
    """Convert SQLAlchemy model instance to a clean dict suitable for Parquet export."""
    data = {}
    for col in obj.__table__.columns:
        val = getattr(obj, col.name)
        if isinstance(val, (datetime, date)):
            val = val.isoformat()
        elif hasattr(val, "value"):  # Enum support
            val = str(val.value)
        elif type(val).__name__ == "Decimal":
            val = float(val)
        data[col.name] = val
    return data


def export_table_to_parquet_bytes(db: Session, model_class: Any, end_cutoff_datetime: datetime) -> Tuple[bytes, int]:
    """
    Query records from model_class up to end_cutoff_datetime and serialize them to Parquet format.
    Returns (parquet_bytes, record_count).
    """
    query = db.query(model_class)
    if hasattr(model_class, "created_at"):
        query = query.filter(model_class.created_at <= end_cutoff_datetime)
    
    rows = query.all()
    record_count = len(rows)

    records = [model_to_dict(row) for row in rows]

    try:
        import pandas as pd
        import pyarrow as pa
        import pyarrow.parquet as pq

        if records:
            df = pd.DataFrame(records)
            table = pa.Table.from_pandas(df)
        else:
            # Empty table schema from model columns
            cols = [col.name for col in model_class.__table__.columns]
            df = pd.DataFrame(columns=cols)
            table = pa.Table.from_pandas(df)

        buf = io.BytesIO()
        pq.write_table(table, buf, compression="snappy")
        buf.seek(0)
        return buf.getvalue(), record_count
    except Exception as exc:
        logger.exception(
            "[PARQUET EXPORT ERROR] Failed to export table %s",
            model_class.__tablename__,
        )
        raise RuntimeError(
            f"Parquet export failed for {model_class.__tablename__}"
        ) from exc


def run_daily_parquet_rolling_backup(db: Session, target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Executes daily rolling backup of transactional & operational data up to target_date (defaults to yesterday).
    Exports operational tables into Apache Parquet format and uploads them to 'Permanent Files - Bucket' (s3_bucket_name)
    under a daily directory structure: rolling_backups/parquet/YYYY-MM-DD/<table_name>.parquet
    """
    from app.models.order import Order, OrderItem
    from app.models.payment import Payment
    from app.models.attendance import Attendance
    from app.models.timesheet import Timesheet
    from app.models.expense import Expense
    from app.models.material_request import MaterialRequest, MaterialRequestHistoryLog
    from app.models.procurement import VendorQuotation, WorkOrder
    from app.models.inventory import StockMovement

    cutoff_date = target_date or (datetime.utcnow().date() - timedelta(days=1))
    date_str = cutoff_date.strftime("%Y-%m-%d")
    end_cutoff_datetime = datetime.combine(cutoff_date, time.max)

    target_models = [
        Order,
        OrderItem,
        Payment,
        Attendance,
        Timesheet,
        Expense,
        MaterialRequest,
        MaterialRequestHistoryLog,
        VendorQuotation,
        WorkOrder,
        StockMovement,
    ]

    config = get_s3_config(db)
    is_s3_enabled = config.get("s3_is_enabled")
    if not is_s3_enabled:
        raise ValueError("Parquet Rolling Backup is disabled: Permanent S3 Storage is not enabled in S3 Settings.")

    from app.utils.s3_service import test_s3_connection
    s3_ok, s3_msg = test_s3_connection(config, bucket_type="permanent")
    if not s3_ok:
        raise ValueError(f"Parquet Rolling Backup is disabled: Permanent S3 Storage connection failed ({s3_msg}).")

    s3_endpoint = config.get("s3_endpoint_url")
    s3_bucket = config.get("s3_bucket_name")
    s3_access_key = config.get("s3_access_key_id")
    s3_secret_key = config.get("s3_secret_access_key")
    s3_region = config.get("s3_region_name") or "us-west-004"
    uploaded_files = []
    uploaded_keys = []
    total_records_exported = 0
    if not (s3_bucket and s3_access_key and s3_secret_key):
        raise RuntimeError("Permanent S3 configuration is incomplete.")
    s3_client = _s3_client(config)

    try:
        for model in target_models:
            table_name = model.__tablename__
            parquet_bytes, count = export_table_to_parquet_bytes(
                db, model, end_cutoff_datetime
            )
            object_key = f"{PARQUET_PREFIX}/{date_str}/{table_name}.parquet"
            file_size_bytes = len(parquet_bytes)
            digest = hashlib.sha256(parquet_bytes).hexdigest()
            total_records_exported += count

            if not parquet_bytes:
                raise RuntimeError(f"Empty Parquet payload for {object_key}.")
            s3_client.put_object(
                Bucket=s3_bucket,
                Key=object_key,
                Body=parquet_bytes,
                ContentType="application/vnd.apache.parquet",
                ServerSideEncryption="AES256",
                Metadata={"sha256": digest, "record-count": str(count)},
            )
            uploaded_keys.append(object_key)
            stored = s3_client.head_object(Bucket=s3_bucket, Key=object_key)
            if stored.get("ContentLength") != file_size_bytes:
                raise RuntimeError(
                    f"Stored object size mismatch for {object_key}: "
                    f"{stored.get('ContentLength')} != {file_size_bytes}"
                )
            stored_digest = (stored.get("Metadata") or {}).get("sha256")
            if not stored_digest or not hmac.compare_digest(stored_digest, digest):
                raise RuntimeError(
                    f"Stored object checksum metadata mismatch for {object_key}."
                )

            uploaded_files.append({
                "table_name": table_name,
                "object_key": object_key,
                "record_count": count,
                "size_bytes": file_size_bytes,
                "sha256": digest,
                "storage_type": "S3 (Permanent Bucket, private)",
            })

        manifest = {
            "format_version": 1,
            "backup_date": date_str,
            "cutoff_datetime": end_cutoff_datetime.isoformat(),
            "created_at": datetime.utcnow().isoformat() + "Z",
            "files": uploaded_files,
        }
        manifest["signature"] = _manifest_signature(manifest)
        manifest_bytes = json.dumps(
            manifest, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        manifest_key = f"{PARQUET_PREFIX}/{date_str}/manifest.json"
        s3_client.put_object(
            Bucket=s3_bucket,
            Key=manifest_key,
            Body=manifest_bytes,
            ContentType="application/json",
            ServerSideEncryption="AES256",
            Metadata={"sha256": hashlib.sha256(manifest_bytes).hexdigest()},
        )
        uploaded_keys.append(manifest_key)
        # A backup is complete only when it can immediately survive a full
        # authenticated download/decode verification.
        verify_parquet_backup(s3_client, s3_bucket, cutoff_date)
    except Exception as exc:
        logger.exception("[PARQUET ROLLING BACKUP ERROR] Incomplete backup removed")
        if uploaded_keys:
            try:
                s3_client.delete_objects(
                    Bucket=s3_bucket,
                    Delete={"Objects": [{"Key": key} for key in uploaded_keys]},
                )
            except Exception:
                logger.exception("Failed cleaning incomplete Parquet backup prefix")
        raise RuntimeError(
            "Parquet upload/integrity verification failed; no records were archived."
        ) from exc

    # Stage 1: Soft-archive backed up records in SQL database
    soft_archived_count = soft_archive_backed_up_records(db, end_cutoff_datetime)

    # Stage 2: Hard-purge expired records older than retention window (default 90 days)
    purge_res = run_hard_purge_expired_records(db)
    retained_object_deletions = enforce_parquet_object_retention(
        s3_client, s3_bucket
    )

    result = {
        "status": "success",
        "cutoff_date": date_str,
        "directory_structure": f"rolling_backups/parquet/{date_str}/",
        "target_bucket": s3_bucket if (is_s3_enabled and s3_bucket) else "Local Disk Storage",
        "total_tables": len(uploaded_files),
        "total_records": total_records_exported,
        "soft_archived_count": soft_archived_count,
        "hard_purged_count": purge_res.get("total_purged", 0),
        "retention_days": purge_res.get("retention_days", 90),
        "parquet_retention_days": settings.parquet_backup_retention_days,
        "retained_object_deletions": retained_object_deletions,
        "manifest_key": f"{PARQUET_PREFIX}/{date_str}/manifest.json",
        "files": uploaded_files,
        "executed_at": datetime.utcnow().isoformat(),
    }
    logger.info(f"[PARQUET ROLLING BACKUP COMPLETE] Date: {date_str}, Tables: {len(uploaded_files)}, Total Rows: {total_records_exported}")
    return result


def soft_archive_backed_up_records(db: Session, end_cutoff_datetime: datetime) -> int:
    """
    Stage 1: Soft-Archival post-Parquet S3 upload.
    Marks all exported records up to end_cutoff_datetime as soft-archived (is_archived = True, archived_at = NOW()).
    """
    from app.models.order import Order, OrderItem
    from app.models.payment import Payment
    from app.models.attendance import Attendance
    from app.models.timesheet import Timesheet
    from app.models.expense import Expense
    from app.models.material_request import MaterialRequest, MaterialRequestHistoryLog
    from app.models.procurement import VendorQuotation, WorkOrder
    from app.models.inventory import StockMovement

    target_models = [
        OrderItem,
        Order,
        Payment,
        Attendance,
        Timesheet,
        Expense,
        MaterialRequestHistoryLog,
        MaterialRequest,
        VendorQuotation,
        WorkOrder,
        StockMovement,
    ]

    now_utc = datetime.utcnow()
    total_soft_archived = 0

    for model in target_models:
        if hasattr(model, "is_archived") and hasattr(model, "created_at"):
            query = db.query(model).filter(
                model.is_archived == False,
                model.created_at <= end_cutoff_datetime,
            )
            updated_count = query.update(
                {model.is_archived: True, model.archived_at: now_utc},
                synchronize_session=False,
            )
            total_soft_archived += updated_count
    
    db.commit()
    logger.info(f"[PARQUET HYBRID ARCHIVAL] Soft-archived {total_soft_archived} records up to {end_cutoff_datetime.isoformat()}")
    return total_soft_archived


def run_hard_purge_expired_records(db: Session) -> Dict[str, Any]:
    """
    Stage 2: Hard Retention Purge.
    Safely deletes records from SQL database that meet ALL 3 criteria:
      1. is_archived == True (verifying they were backed up to S3 Parquet)
      2. created_at <= hard_cutoff_datetime (older than retention_days, default 90 days)
      3. Permanent S3 Bucket is enabled and connection is healthy.
    Child detail tables are deleted before parent tables to prevent foreign key errors.
    """
    config = get_s3_config(db)
    if not config.get("s3_is_enabled"):
        return {"status": "skipped", "message": "Hard retention purge skipped: Permanent S3 Bucket is not enabled.", "total_purged": 0}

    from app.utils.s3_service import test_s3_connection
    s3_ok, s3_msg = test_s3_connection(config, bucket_type="permanent")
    if not s3_ok:
        return {"status": "skipped", "message": f"Hard retention purge skipped: S3 connection failed ({s3_msg}).", "total_purged": 0}

    from app.models.company import SystemConfiguration
    sys_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    retention_days = sys_config.archival_retention_days if (sys_config and sys_config.archival_retention_days) else 90

    hard_cutoff_datetime = datetime.utcnow() - timedelta(days=retention_days)

    from app.models.order import Order, OrderItem, OrderHistoryLog
    from app.models.payment import Payment
    from app.models.attendance import Attendance
    from app.models.timesheet import Timesheet
    from app.models.expense import Expense
    from app.models.material_request import MaterialRequest, MaterialRequestHistoryLog
    from app.models.procurement import VendorQuotation, WorkOrder
    from app.models.inventory import StockMovement

    purge_sequence = [
        OrderItem,
        OrderHistoryLog,
        Payment,
        MaterialRequestHistoryLog,
        VendorQuotation,
        WorkOrder,
        Order,
        Attendance,
        Timesheet,
        Expense,
        MaterialRequest,
        StockMovement,
    ]

    total_purged = 0
    purged_by_table = {}

    for model in purge_sequence:
        if hasattr(model, "is_archived") and hasattr(model, "created_at"):
            query = db.query(model).filter(
                model.is_archived == True,
                model.created_at <= hard_cutoff_datetime,
            )
            count = query.delete(synchronize_session=False)
            total_purged += count
            purged_by_table[model.__tablename__] = count
    
    db.commit()
    logger.info(f"[PARQUET HYBRID ARCHIVAL] Hard-purged {total_purged} expired records older than {retention_days} days")
    return {
        "status": "success",
        "retention_days": retention_days,
        "cutoff_datetime": hard_cutoff_datetime.isoformat(),
        "total_purged": total_purged,
        "purged_by_table": purged_by_table,
    }
