import io
from datetime import date, timedelta

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.order import Order
from app.services import parquet_backup_service as parquet
from app.utils import s3_service


class MemoryBody:
    def __init__(self, value):
        self.value = value

    def read(self):
        return self.value


class MemoryS3:
    def __init__(self):
        self.objects = {}
        self.metadata = {}

    def put_object(self, Bucket, Key, Body, Metadata=None, **_kwargs):
        value = Body.read() if hasattr(Body, "read") else bytes(Body)
        self.objects[(Bucket, Key)] = value
        self.metadata[(Bucket, Key)] = Metadata or {}

    def head_object(self, Bucket, Key):
        value = self.objects[(Bucket, Key)]
        return {
            "ContentLength": len(value),
            "Metadata": self.metadata[(Bucket, Key)],
        }

    def get_object(self, Bucket, Key):
        return {"Body": MemoryBody(self.objects[(Bucket, Key)])}

    def delete_objects(self, Bucket, Delete):
        for item in Delete["Objects"]:
            self.objects.pop((Bucket, item["Key"]), None)
            self.metadata.pop((Bucket, item["Key"]), None)

    def list_objects_v2(self, Bucket, Prefix):
        return {
            "Contents": [
                {"Key": key}
                for stored_bucket, key in self.objects
                if stored_bucket == Bucket and key.startswith(Prefix)
            ]
        }


@pytest.fixture()
def parquet_storage(monkeypatch):
    client = MemoryS3()
    config = {
        "s3_is_enabled": True,
        "s3_endpoint_url": "https://storage.example.test",
        "s3_bucket_name": "private-backups",
        "s3_access_key_id": "access",
        "s3_secret_access_key": "secret",
        "s3_region_name": "test",
    }
    monkeypatch.setattr(parquet, "get_s3_config", lambda _db: config)
    monkeypatch.setattr(
        s3_service, "test_s3_connection", lambda *_args, **_kwargs: (True, "ok")
    )
    monkeypatch.setattr(parquet, "_s3_client", lambda _config: client)
    monkeypatch.setattr(settings, "backup_encryption_key", "p" * 32)
    monkeypatch.setattr(settings, "parquet_backup_retention_days", 365)
    return client, config["s3_bucket_name"]


def test_signed_parquet_backup_integrity_corruption_and_clean_restore(
    db_session, operational_data, parquet_storage, monkeypatch
):
    client, bucket = parquet_storage
    monkeypatch.setattr(
        parquet, "soft_archive_backed_up_records", lambda *_args: 0
    )
    monkeypatch.setattr(
        parquet,
        "run_hard_purge_expired_records",
        lambda *_args: {"total_purged": 0, "retention_days": 90},
    )
    backup_date = date(2026, 7, 30)
    result = parquet.run_daily_parquet_rolling_backup(
        db_session, target_date=backup_date
    )

    assert result["status"] == "success"
    assert result["total_tables"] == 11
    assert result["manifest_key"].endswith("/manifest.json")
    recovered = parquet.verify_parquet_backup(client, bucket, backup_date)
    assert len(recovered["orders"]) >= 1
    assert len(recovered["order_items"]) >= 1

    clean_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(clean_engine)
    clean_db = sessionmaker(bind=clean_engine)()
    try:
        restored = parquet.restore_verified_parquet_backup(
            clean_db, {"orders": recovered["orders"]}, {"orders": Order}
        )
        assert restored["orders"] == len(recovered["orders"])
        assert clean_db.query(Order).count() == len(recovered["orders"])
    finally:
        clean_db.close()
        clean_engine.dispose()

    order_key = next(
        key for stored_bucket, key in client.objects
        if stored_bucket == bucket and key.endswith("/orders.parquet")
    )
    client.objects[(bucket, order_key)] += b"corruption"
    with pytest.raises(RuntimeError, match="checksum verification failed"):
        parquet.verify_parquet_backup(client, bucket, backup_date)


def test_parquet_retention_deletes_only_expired_date_prefixes(
    parquet_storage, monkeypatch
):
    client, bucket = parquet_storage
    today = date(2026, 7, 29)
    expired = (today - timedelta(days=366)).isoformat()
    retained = (today - timedelta(days=365)).isoformat()
    client.put_object(
        Bucket=bucket,
        Key=f"{parquet.PARQUET_PREFIX}/{expired}/manifest.json",
        Body=b"old",
    )
    client.put_object(
        Bucket=bucket,
        Key=f"{parquet.PARQUET_PREFIX}/{retained}/manifest.json",
        Body=b"boundary",
    )
    client.put_object(Bucket=bucket, Key="unrelated/file", Body=b"keep")

    assert parquet.enforce_parquet_object_retention(
        client, bucket, now=today
    ) == 1
    assert (bucket, f"{parquet.PARQUET_PREFIX}/{expired}/manifest.json") not in client.objects
    assert (bucket, f"{parquet.PARQUET_PREFIX}/{retained}/manifest.json") in client.objects
    assert (bucket, "unrelated/file") in client.objects
