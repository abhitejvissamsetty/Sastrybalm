import os
import logging
from datetime import datetime
from typing import Optional, Tuple
from sqlalchemy.orm import Session

from app.utils.encryption import decrypt

logger = logging.getLogger(__name__)


def get_s3_config(db: Session) -> dict:
    """Fetch active S3 configuration from system_configuration table."""
    from app.models.company import SystemConfiguration
    sys_config = db.query(SystemConfiguration).filter(SystemConfiguration.id == 1).first()
    if not sys_config:
        return {"s3_is_enabled": False, "s3_files_is_enabled": False}

    sec_key = sys_config.s3_secret_access_key or ""
    if sec_key.startswith("gAAAAA"):
        try:
            sec_key = decrypt(sec_key)
        except Exception:
            pass

    files_sec_key = sys_config.s3_files_secret_access_key or ""
    if files_sec_key.startswith("gAAAAA"):
        try:
            files_sec_key = decrypt(files_sec_key)
        except Exception:
            pass

    return {
        # 1. Images Bucket Config
        "s3_is_enabled": bool(sys_config.s3_is_enabled),
        "s3_endpoint_url": sys_config.s3_endpoint_url or "",
        "s3_bucket_name": sys_config.s3_bucket_name or "",
        "s3_access_key_id": sys_config.s3_access_key_id or "",
        "s3_secret_access_key": sec_key,
        "s3_region_name": sys_config.s3_region_name or "us-west-004",
        "s3_public_url_prefix": sys_config.s3_public_url_prefix or "",

        # 2. Files & Documents Bucket Config
        "s3_files_is_enabled": bool(sys_config.s3_files_is_enabled),
        "s3_files_endpoint_url": sys_config.s3_files_endpoint_url or "",
        "s3_files_bucket_name": sys_config.s3_files_bucket_name or "",
        "s3_files_access_key_id": sys_config.s3_files_access_key_id or "",
        "s3_files_secret_access_key": files_sec_key,
        "s3_files_region_name": sys_config.s3_files_region_name or "us-west-004",
        "s3_files_public_url_prefix": sys_config.s3_files_public_url_prefix or "",
    }


def upload_image_file(
    db: Session,
    file_bytes: bytes,
    original_filename: str,
    folder_prefix: str = "general",
    content_type: str = "image/jpeg",
    bucket_type: str = "images",
) -> str:
    """
    Unified file upload handler for outlet images, material request images, QC photos, asset pictures, and files/documents.
    Uploads to Backblaze B2 S3 bucket using dedicated bucket credentials based on bucket_type ("images" vs "files").
    Falls back to local static disk storage only in non-production environments.
    """
    ext = os.path.splitext(original_filename)[1] or ".jpg"
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    clean_prefix = folder_prefix.strip("/").replace(" ", "_")
    object_key = f"{clean_prefix}/{timestamp_str}_{os.urandom(4).hex()}{ext}"

    config = get_s3_config(db)

    # Determine credentials based on bucket_type
    if bucket_type in ("temporary", "files"):
        is_enabled = config.get("s3_files_is_enabled")
        endpoint_url = config.get("s3_files_endpoint_url")
        target_bucket = config.get("s3_files_bucket_name")
        access_key = config.get("s3_files_access_key_id")
        secret_key = config.get("s3_files_secret_access_key")
        region_name = config.get("s3_files_region_name") or "us-west-004"
        public_prefix = config.get("s3_files_public_url_prefix")
    else:
        is_enabled = config.get("s3_is_enabled")
        endpoint_url = config.get("s3_endpoint_url")
        target_bucket = config.get("s3_bucket_name")
        access_key = config.get("s3_access_key_id")
        secret_key = config.get("s3_secret_access_key")
        region_name = config.get("s3_region_name") or "us-west-004"
        public_prefix = config.get("s3_public_url_prefix")

    # Attempt S3 Upload if enabled & configured
    if is_enabled and target_bucket and access_key and secret_key:
        try:
            import boto3
            s3_client = boto3.client(
                "s3",
                endpoint_url=endpoint_url or None,
                aws_access_key_id=access_key,
                aws_secret_access_key=secret_key,
                region_name=region_name,
            )

            s3_client.put_object(
                Bucket=target_bucket,
                Key=object_key,
                Body=file_bytes,
                ContentType=content_type,
            )

            if public_prefix:
                return f"{public_prefix.rstrip('/')}/{object_key}"

            ep = (endpoint_url or "").rstrip("/")
            if ep:
                return f"{ep}/{target_bucket}/{object_key}"
            return f"https://{target_bucket}.s3.{region_name}.backblazeb2.com/{object_key}"

        except Exception as exc:
            logger.exception(
                "[S3 UPLOAD ERROR] Failed to upload object to bucket '%s'",
                target_bucket,
            )
            from app.config import settings
            if settings.is_production:
                raise RuntimeError("Object storage upload failed.") from exc

    # Local Disk Fallback
    from app.config import settings
    if settings.is_production:
        raise RuntimeError(
            "Object storage is required in production; local upload fallback is disabled."
        )
    local_dir = os.path.join("app", "static", "uploads", clean_prefix)
    os.makedirs(local_dir, exist_ok=True)
    filename = f"{timestamp_str}_{os.urandom(4).hex()}{ext}"
    local_path = os.path.join(local_dir, filename)

    with open(local_path, "wb") as f:
        f.write(file_bytes)

    return f"/static/uploads/{clean_prefix}/{filename}"


def test_s3_connection(config: dict, bucket_type: str = "permanent") -> Tuple[bool, str]:
    """Test connection to Backblaze B2 S3 bucket for Permanent Files or Temporary Files."""
    if bucket_type in ("temporary", "files"):
        bucket_name = config.get("s3_files_bucket_name")
        endpoint_url = config.get("s3_files_endpoint_url")
        access_key = config.get("s3_files_access_key_id")
        secret_key = config.get("s3_files_secret_access_key")
        region_name = config.get("s3_files_region_name") or "us-west-004"
        label = "Temporary Files"
    else:
        bucket_name = config.get("s3_bucket_name")
        endpoint_url = config.get("s3_endpoint_url")
        access_key = config.get("s3_access_key_id")
        secret_key = config.get("s3_secret_access_key")
        region_name = config.get("s3_region_name") or "us-west-004"
        label = "Permanent Files"

    if not bucket_name or not access_key or not secret_key:
        return False, f"{label} Bucket configuration is incomplete. Please specify Bucket Name, Access Key ID, and Secret Access Key."

    try:
        import boto3
        s3_client = boto3.client(
            "s3",
            endpoint_url=endpoint_url or None,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region_name,
        )
        s3_client.head_bucket(Bucket=bucket_name)
        return True, f"Successfully connected to {label} Bucket '{bucket_name}'!"
    except Exception as exc:
        return False, f"{label} Bucket Connection Failed: {exc}"
