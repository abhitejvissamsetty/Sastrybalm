"""
S3 / MinIO Storage Adapter — Handles image and file uploads to S3/MinIO bucket,
daily operational data backups, scheduled analytics CSV reports, and pre-signed URLs.
"""
import os
import logging
from typing import Optional, Tuple
from datetime import datetime, timedelta

logger = logging.getLogger("sastrybalm.s3")


def get_s3_client(s3_config: dict):
    """Instantiate boto3 S3 client with configured endpoint and credentials."""
    import boto3
    from botocore.config import Config

    endpoint_url = s3_config.get("s3_endpoint")
    access_key = s3_config.get("s3_access_key")
    secret_key = s3_config.get("s3_secret_key")
    region_name = s3_config.get("s3_region", "us-east-1")
    use_ssl = s3_config.get("s3_use_ssl", "true").lower() in ("true", "1", "yes")

    if endpoint_url and not endpoint_url.startswith("http"):
        protocol = "https://" if use_ssl else "http://"
        endpoint_url = f"{protocol}{endpoint_url}"

    session = boto3.session.Session()
    client = session.client(
        "s3",
        region_name=region_name,
        endpoint_url=endpoint_url or None,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        config=Config(signature_version="s3v4")
    )
    return client


def test_s3_connection(s3_config: dict) -> Tuple[bool, str]:
    """Test S3 / MinIO credentials and bucket access."""
    bucket = s3_config.get("s3_bucket")
    if not bucket:
        return False, "S3 Bucket name is missing"
    
    try:
        client = get_s3_client(s3_config)
        # Attempt head_bucket or list_objects_v2
        client.head_bucket(Bucket=bucket)
        return True, f"Successfully connected to bucket '{bucket}'"
    except Exception as e:
        return False, str(e)


def upload_file_to_s3(
    file_bytes: bytes,
    object_name: str,
    content_type: str = "application/octet-stream",
    s3_config: Optional[dict] = None
) -> Tuple[bool, str]:
    """
    Upload raw bytes to S3/MinIO. Returns (success, url_or_key).
    If s3_config is not provided, tries to fetch from system settings in DB.
    """
    if not s3_config:
        from app.database import SessionLocal
        from app.models.company import SystemSetting
        db = SessionLocal()
        try:
            s3_config = {}
            for k in ["s3_endpoint", "s3_bucket", "s3_access_key", "s3_secret_key", "s3_region", "s3_use_ssl"]:
                s = db.query(SystemSetting).filter(SystemSetting.key == k).first()
                if s:
                    s3_config[k] = s.value
        finally:
            db.close()

    bucket = s3_config.get("s3_bucket")
    if not bucket or not s3_config.get("s3_access_key"):
        # Fallback to local media saving
        local_dir = os.path.join("app", "static", "uploads")
        os.makedirs(local_dir, exist_ok=True)
        local_path = os.path.join(local_dir, os.path.basename(object_name))
        with open(local_path, "wb") as f:
            f.write(file_bytes)
        return True, f"/static/uploads/{os.path.basename(object_name)}"

    try:
        client = get_s3_client(s3_config)
        client.put_object(
            Bucket=bucket,
            Key=object_name,
            Body=file_bytes,
            ContentType=content_type
        )
        # Return pre-signed URL or public URL
        url = generate_presigned_url(object_name, expiration_seconds=86400 * 7, s3_config=s3_config)
        return True, url
    except Exception as e:
        logger.error(f"S3 upload error for '{object_name}': {e}")
        return False, str(e)


def generate_presigned_url(object_name: str, expiration_seconds: int = 3600, s3_config: Optional[dict] = None) -> str:
    """Generate a time-bound pre-signed URL for downloading an object from S3/MinIO."""
    if not s3_config:
        from app.database import SessionLocal
        from app.models.company import SystemSetting
        db = SessionLocal()
        try:
            s3_config = {}
            for k in ["s3_endpoint", "s3_bucket", "s3_access_key", "s3_secret_key", "s3_region", "s3_use_ssl"]:
                s = db.query(SystemSetting).filter(SystemSetting.key == k).first()
                if s:
                    s3_config[k] = s.value
        finally:
            db.close()

    bucket = s3_config.get("s3_bucket")
    if not bucket:
        return f"/static/uploads/{os.path.basename(object_name)}"

    try:
        client = get_s3_client(s3_config)
        url = client.generate_presigned_url(
            "get_object",
            Params={"Bucket": bucket, "Key": object_name},
            ExpiresIn=expiration_seconds
        )
        return url
    except Exception as e:
        logger.error(f"Error generating presigned URL for '{object_name}': {e}")
        return f"/static/uploads/{os.path.basename(object_name)}"
