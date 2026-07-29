# Disaster-Recovery Drill — 2026-07-29

## Scope

This drill verified encrypted SQL backup creation, private local retention,
decryption, restoration into an isolated clean MySQL database, Alembic
convergence, and data integrity. The production database was not modified.

## Evidence

- Backup: `safar_sfa_backup_20260729_142358.sql.enc`
- File mode: `0600`
- Encrypted size: `120056` bytes
- SHA-256:
  `c18c3578a69ebebf1e7bbe9bf6f6b6f9c8f42a32f41689f667ed711f17a6b52e`
- Isolated restore database: `safar_restore_drill_20260729`
- Restore result: `restore-ok`
- Source database: 59 tables, 122 total rows, 5 users, 0 orders
- Restored database: 59 tables, 122 total rows, 5 users, 0 orders
- Source Alembic revision: `a48e9f4ea7f2`
- Restored Alembic revision: `a48e9f4ea7f2`
- Temporary restore database was dropped after verification.

The application’s automated backup tests also verify encryption-key isolation,
wrong-key rejection, private S3 upload metadata and integrity checks, successful
restore through the MySQL client followed by Alembic upgrade, five-copy
retention, and fail-closed Parquet behavior.

## Recovery procedure

Follow [MIGRATION_AND_RECOVERY_RUNBOOK.md](MIGRATION_AND_RECOVERY_RUNBOOK.md).
Always restore into an isolated database first, compare table and critical
record counts, verify the `alembic_version`, and only then authorize a
production cutover.
