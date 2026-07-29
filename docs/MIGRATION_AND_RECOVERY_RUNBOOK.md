# Migration and recovery runbook

## Deployment rule

1. Put the application into maintenance mode and stop the application and
   scheduler processes.
2. Create an encrypted SQL backup. A production backup is successful only
   after the private permanent S3 object is uploaded with server-side
   encryption and its byte length and SHA-256 metadata are verified.
3. Record the encrypted backup object key, checksum, current Alembic revision,
   and database row counts.
4. Run `alembic upgrade head` as a separate deployment step.
5. Run `alembic current` and `alembic check`. Start application processes only
   when the expected head is reported and no ORM drift is detected.

Migration errors are fatal. Never stamp a failed or partially migrated database
to head.

## Downgrade policy

Ordinary revisions must support a tested Alembic downgrade. Revision
`1b0b2e1aa02e` is intentionally forward-only because it removes obsolete legacy
structures and MySQL DDL is non-transactional. Its `downgrade()` refuses to run.
Rollback across that boundary means restoring the verified encrypted
pre-deployment SQL backup, then deploying the prior application version.

## Interrupted migration recovery

1. Keep the application and scheduler stopped.
2. Do not rerun a migration after an unknown partial MySQL DDL failure.
3. Restore the verified encrypted pre-deployment backup into a new clean
   database first.
4. Verify its checksum, Alembic revision, representative row counts, and
   application authentication.
5. Switch the application database only after the restored database passes
   verification. Preserve the failed database read-only for incident analysis.

`restore_sql_backup()` decrypts to a mode-0600 temporary file, fails on any SQL
statement error, upgrades with Alembic, and propagates migration failures.

## Verified drill — 2026-07-29

- Clean schema upgraded through head and `alembic check` reported no operations.
- Schema downgraded to base and re-upgraded through the pre-normalization chain.
- The normalization revision was verified as a no-op on a clean schema.
- A real legacy database normalization was deliberately interrupted by invalid
  foreign-key ordering.
- The database was restored from
  `safar_sfa_backup_20260729_125057.sql.enc`, normalization was reapplied, and
  `alembic check` reported no operations.
- The retained encrypted copy has SHA-256
  `8fb0011666a7abdac74eccda3424a7f8e8c97440421a1be7670418a9d890d919`.
- Plaintext SQL and publicly served Parquet legacy backups were removed.

