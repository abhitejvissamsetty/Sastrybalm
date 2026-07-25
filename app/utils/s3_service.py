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
        return {"s3_is_enabled": False}

    sec_key = sys_config.s3_secret_access_key or ""
    if sec_key.startswith("gAAAAA"):
        try:
            sec_key = decrypt(sec_key)
        except Exception:
            pass

    return {
        "s3_is_enabled": bool(sys_config.s3_is_enabled),
        "s3_endpoint_url": sys_config.s3_endpoint_url or "",
        "s3_bucket_name": sys_config.s3_bucket_name or "",
        "s3_access_key_id": sys_config.s3_access_key_id or "",
        "s3_secret_access_key": sec_key,
        "s3_region_name": sys_config.s3_region_name or "us-west-004",
        "s3_public_url_prefix": sys_config.s3_public_url_prefix or "",
    }


def upload_image_file(
    db: Session,
    file_bytes: bytes,
    original_filename: str,
    folder_prefix: str = "general",
    content_type: str = "image/jpeg",
) -> str:
    """
    Unified file upload handler for outlet images, material request images, QC photos, and asset pictures.
    Uploads to Backblaze B2 S3 bucket if enabled in settings, otherwise falls back to local static disk storage.
    """
    ext = os.path.splitext(original_filename)[1] or ".jpg"
    timestamp_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    clean_prefix = folder_prefix.strip("/").replace(" ", "_")
    object_key = f"{clean_prefix}/{timestamp_str}_{os.urandom(4).hex()}{ext}"

    config = get_s3_config(db)

    # Attempt S3 Upload if enabled & configured
    if config.get("s3_is_enabled") and config.get("s3_bucket_name") and config.get("s3_access_key_id"):
        try:
            import boto3
            s3_client = boto3.client(
                "s3",
                endpoint_url=config["s3_endpoint_url"] or None,
                aws_access_key_id=config["s3_access_key_id"],
                aws_secret_access_key=config["s3_secret_access_key"],
                region_name=config["s3_region_name"] or "us-west-004",
            )

            s3_client.put_object(
                Bucket=config["s3_bucket_name"],
                Key=object_key,
                Body=file_bytes,
                ContentType=content_type,
            )

            if config.get("s3_public_url_prefix"):
                public_prefix = config["s3_public_url_prefix"].rstrip("/")
                return f"{public_prefix}/{object_key}"

            endpoint = (config["s3_endpoint_url"] or "").rstrip("/")
            if endpoint:
                return f"{endpoint}/{config['s3_bucket_name']}/{object_key}"
            return f"https://{config['s3_bucket_name']}.s3.{config['s3_region_name']}.backblazeb2.com/{object_key}"

        except Exception as exc:
            logger.error(f"[S3 UPLOAD ERROR] Failed to upload to Backblaze B2 S3: {exc}. Falling back to local disk storage.")

    # Local Disk Fallback
    local_dir = os.path.join("app", "static", "uploads", clean_prefix)
    os.makedirs(local_dir, exist_ok=True)
    filename = f"{timestamp_str}_{os.urandom(4).hex()}{ext}"
    local_path = os.path.join(local_dir, filename)

    with open(local_path, "wb") as f:
        f.write(file_bytes)

    return f"/static/uploads/{clean_prefix}/{filename}"


def test_s3_connection(config: dict) -> Tuple[bool, str]:
    """Test connection to Backblaze B2 S3 bucket."""
    try:
        import boto3
        s3_client = boto3.client(
            "s3",
            endpoint_url=config.get("s3_endpoint_url") or None,
            aws_access_key_id=config.get("s3_access_key_id"),
            aws_secret_access_key=config.get("s3_secret_access_key"),
            region_name=config.get("s3_region_name") or "us-west-004",
        )
        s3_client.head_bucket(Bucket=config.get("s3_bucket_name"))
        return True, f"Successfully connected to Backblaze B2 bucket '{config.get('s3_bucket_name')}'!"
    except Exception as exc:
        return False, f"Backblaze B2 S3 Connection Failed: {exc}"
