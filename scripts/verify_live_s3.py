"""Destructive, prefix-scoped verification of the production S3 release gate.

The probe only creates and deletes objects under ``release-verification/``.
It never prints credentials. Run it with both permanent and short-lived
credentials plus a deliberately unauthorized identity.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from typing import Any

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError


@dataclass(frozen=True)
class S3Identity:
    access_key: str
    secret_key: str
    session_token: str | None = None


def required(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def client(identity: S3Identity):
    return boto3.client(
        "s3",
        endpoint_url=required("S3_ENDPOINT"),
        region_name=required("S3_REGION"),
        aws_access_key_id=identity.access_key,
        aws_secret_access_key=identity.secret_key,
        aws_session_token=identity.session_token,
        config=Config(
            signature_version="s3v4",
            connect_timeout=5,
            read_timeout=15,
            retries={"max_attempts": 2, "mode": "standard"},
        ),
    )


def assert_not_public(s3, bucket: str) -> None:
    block = s3.get_public_access_block(Bucket=bucket)[
        "PublicAccessBlockConfiguration"
    ]
    required_flags = (
        "BlockPublicAcls",
        "IgnorePublicAcls",
        "BlockPublicPolicy",
        "RestrictPublicBuckets",
    )
    if not all(block.get(flag) is True for flag in required_flags):
        raise RuntimeError("bucket public-access block is incomplete")

    status = s3.get_bucket_policy_status(Bucket=bucket)["PolicyStatus"]
    if status.get("IsPublic") is not False:
        raise RuntimeError("bucket policy is public")


def assert_round_trip(
    s3,
    bucket: str,
    key: str,
    payload: bytes,
    *,
    verify_expiry: bool,
) -> dict[str, Any]:
    s3.put_object(
        Bucket=bucket,
        Key=key,
        Body=payload,
        ContentType="application/octet-stream",
        ServerSideEncryption="AES256",
    )
    downloaded = s3.get_object(Bucket=bucket, Key=key)["Body"].read()
    if downloaded != payload:
        raise RuntimeError(f"download mismatch for {key}")

    url = s3.generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=2,
    )
    with urllib.request.urlopen(url, timeout=15) as response:  # nosec B310
        if response.read() != payload:
            raise RuntimeError(f"presigned download mismatch for {key}")

    expiry_verified = False
    if verify_expiry:
        time.sleep(3)
        try:
            urllib.request.urlopen(url, timeout=15)  # nosec B310
        except urllib.error.HTTPError as exc:
            if exc.code not in (400, 403):
                raise
            expiry_verified = True
        if not expiry_verified:
            raise RuntimeError("presigned URL remained usable after expiry")

    s3.delete_object(Bucket=bucket, Key=key)
    try:
        s3.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status not in (403, 404):
            raise
    else:
        raise RuntimeError(f"deleted object still exists: {key}")

    return {
        "upload": True,
        "authenticated_download": True,
        "presigned_download": True,
        "presigned_expiry": expiry_verified,
        "deletion": True,
    }


def assert_isolation(unauthorized_s3, bucket: str, key: str) -> None:
    try:
        unauthorized_s3.get_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        status = exc.response.get("ResponseMetadata", {}).get("HTTPStatusCode")
        if status not in (403, 404):
            raise
    else:
        raise RuntimeError("unauthorized identity could read verification object")


def main() -> None:
    bucket = required("S3_BUCKET")
    permanent = S3Identity(
        required("S3_ACCESS_KEY"),
        required("S3_SECRET_KEY"),
    )
    temporary = S3Identity(
        required("S3_TEMP_ACCESS_KEY"),
        required("S3_TEMP_SECRET_KEY"),
        required("S3_TEMP_SESSION_TOKEN"),
    )
    unauthorized = S3Identity(
        required("S3_DENIED_ACCESS_KEY"),
        required("S3_DENIED_SECRET_KEY"),
        os.environ.get("S3_DENIED_SESSION_TOKEN") or None,
    )

    run_id = uuid.uuid4().hex
    permanent_key = f"release-verification/{run_id}/permanent.bin"
    temporary_key = f"release-verification/{run_id}/temporary.bin"
    payload = os.urandom(64)
    permanent_client = client(permanent)
    temporary_client = client(temporary)
    unauthorized_client = client(unauthorized)

    assert_not_public(permanent_client, bucket)
    permanent_client.put_object(
        Bucket=bucket,
        Key=permanent_key,
        Body=payload,
        ServerSideEncryption="AES256",
    )
    try:
        assert_isolation(unauthorized_client, bucket, permanent_key)
    finally:
        permanent_client.delete_object(Bucket=bucket, Key=permanent_key)

    result = {
        "bucket": bucket,
        "endpoint": required("S3_ENDPOINT"),
        "region": required("S3_REGION"),
        "bucket_not_public": True,
        "access_isolation": True,
        "permanent": assert_round_trip(
            permanent_client,
            bucket,
            permanent_key,
            payload,
            verify_expiry=True,
        ),
        "temporary": assert_round_trip(
            temporary_client,
            bucket,
            temporary_key,
            payload,
            verify_expiry=False,
        ),
    }
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"Live S3 verification failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
