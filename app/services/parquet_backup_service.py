import io
import os
import logging
from datetime import datetime, date, timedelta, time
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy.orm import Session
from app.utils.s3_service import get_s3_config

logger = logging.getLogger(__name__)


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
        logger.error(f"[PARQUET EXPORT ERROR] Failed to export table {model_class.__tablename__} to Parquet: {exc}")
        return b"", 0


def run_daily_parquet_rolling_backup(db: Session, target_date: Optional[date] = None) -> Dict[str, Any]:
    """
    Executes daily rolling backup of transactional & operational data up to target_date (defaults to yesterday).
    Exports operational tables into Apache Parquet format and uploads them to 'Permanent Files - Bucket' (s3_bucket_name)
    under a daily directory structure: rolling_backups/parquet/YYYY-MM-DD/<table_name>.parquet
    """
    from app.models.order import Order, OrderItem
    from app.models.payment import Payment
    from app.models.payment_submission import PaymentSubmission
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
        PaymentSubmission,
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
    s3_endpoint = config.get("s3_endpoint_url")
    s3_bucket = config.get("s3_bucket_name")
    s3_access_key = config.get("s3_access_key_id")
    s3_secret_key = config.get("s3_secret_access_key")
    s3_region = config.get("s3_region_name") or "us-west-004"
    s3_public_prefix = config.get("s3_public_url_prefix")

    uploaded_files = []
    total_records_exported = 0

    for model in target_models:
        table_name = model.__tablename__
        parquet_bytes, count = export_table_to_parquet_bytes(db, model, end_cutoff_datetime)
        object_key = f"rolling_backups/parquet/{date_str}/{table_name}.parquet"
        file_size_bytes = len(parquet_bytes)
        total_records_exported += count

        s3_url = None
        if is_s3_enabled and s3_bucket and s3_access_key and s3_secret_key and parquet_bytes:
            try:
                import boto3
                endpoint_url = s3_endpoint
                if endpoint_url and not endpoint_url.startswith("http"):
                    endpoint_url = f"https://{endpoint_url}"

                s3_client = boto3.client(
                    "s3",
                    endpoint_url=endpoint_url or None,
                    aws_access_key_id=s3_access_key,
                    aws_secret_access_key=s3_secret_key,
                    region_name=s3_region,
                )

                s3_client.put_object(
                    Bucket=s3_bucket,
                    Key=object_key,
                    Body=parquet_bytes,
                    ContentType="application/vnd.apache.parquet",
                )

                if s3_public_prefix:
                    s3_url = f"{s3_public_prefix.rstrip('/')}/{object_key}"
                else:
                    ep = (endpoint_url or "").rstrip("/")
                    if ep:
                        s3_url = f"{ep}/{s3_bucket}/{object_key}"
                    else:
                        s3_url = f"https://{s3_bucket}.s3.{s3_region}.backblazeb2.com/{object_key}"
                
                logger.info(f"[PARQUET ROLLING BACKUP] Uploaded '{object_key}' ({count} rows, {file_size_bytes} bytes) to Permanent Bucket '{s3_bucket}'")
            except Exception as exc:
                logger.error(f"[PARQUET ROLLING BACKUP S3 ERROR] Failed uploading '{object_key}': {exc}")

        # Always save local disk copy as fallback/mirror
        local_dir = os.path.join("app", "static", "uploads", "rolling_backups", "parquet", date_str)
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, f"{table_name}.parquet")
        with open(local_path, "wb") as f:
            f.write(parquet_bytes)

        uploaded_files.append({
            "table_name": table_name,
            "object_key": object_key,
            "record_count": count,
            "size_bytes": file_size_bytes,
            "s3_url": s3_url or f"/static/uploads/rolling_backups/parquet/{date_str}/{table_name}.parquet",
            "storage_type": "S3 (Permanent Bucket)" if s3_url else "Local Disk Storage",
        })

    result = {
        "status": "success",
        "cutoff_date": date_str,
        "directory_structure": f"rolling_backups/parquet/{date_str}/",
        "target_bucket": s3_bucket if (is_s3_enabled and s3_bucket) else "Local Disk Storage",
        "total_tables": len(uploaded_files),
        "total_records": total_records_exported,
        "files": uploaded_files,
        "executed_at": datetime.utcnow().isoformat(),
    }
    logger.info(f"[PARQUET ROLLING BACKUP COMPLETE] Date: {date_str}, Tables: {len(uploaded_files)}, Total Rows: {total_records_exported}")
    return result
