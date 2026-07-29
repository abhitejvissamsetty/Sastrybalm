# Parquet backup and recovery drill — 2026-07-29

## Gate exercised

The deterministic operational fixture was exported across all eleven rolling
backup tables. Every object was uploaded privately with AES-256 server-side
encryption metadata, byte length, row count, and SHA-256 digest. A final
manifest was HMAC-signed using the independent backup encryption key.

The backup was not considered complete—and SQL archival was not permitted—
until the manifest and every object were downloaded, authenticated, decoded,
and row-count verified.

## Recovery result

The verified `orders` Parquet data was restored into a newly created empty
database and the restored row count matched the manifest. A deliberately
corrupted Parquet object was then rejected by checksum verification.

The retention drill created an expired backup prefix, a boundary-date prefix,
and an unrelated object. Only the expired prefix was deleted. Production
Parquet retention defaults to 2,555 days and cannot be configured below 365
days.

Automated evidence: `tests/test_parquet_recovery.py` and
`tests/test_backup_safety.py` passed 9/9.

## Production recovery procedure

1. Disable scheduler backup and purge jobs.
2. Select the required date prefix and fetch `manifest.json`.
3. Call `verify_parquet_backup`; stop immediately on signature, checksum,
   length, decode, or row-count failure.
4. Provision an empty database at the current Alembic revision.
5. Restore tables in manifest/model dependency order with
   `restore_verified_parquet_backup`. The restore refuses non-empty target
   tables and rolls back on error.
6. Reconcile restored table counts with the signed manifest.
7. Run application integrity and acceptance suites before directing traffic.
8. Preserve the source objects and drill evidence; do not delete the recovery
   prefix as part of restoration.
