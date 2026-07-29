# Rollback runbook

## Trigger

Rollback on failed readiness, data-integrity risk, critical/high security
regression, sustained budget breach, repeated worker crash, scheduler
duplication, or failed required integration. The incident commander owns the
decision and records the exact trigger time.

## Application-only rollback

1. Re-enable maintenance mode and stop the scheduler.
2. Preserve logs, metrics, traces, and the failing image digest.
3. Deploy the last approved immutable image digest.
4. Do not run an older binary against a schema it does not support.
5. Validate liveness, readiness, schema revision, role smoke checks, and
   scheduler single ownership before reopening traffic.

## Schema or data rollback

Production schema rollback is restore/forward-fix based. Alembic downgrade is
not authorized unless that exact downgrade was rehearsed and approved before
the release.

1. Stop all writers and scheduler jobs.
2. Capture a forensic encrypted backup of the failed state.
3. Provision a clean database.
4. Restore the pre-deploy encrypted SQL backup and verify its SHA-256 metadata.
5. If recovery requires rolling data, authenticate the signed Parquet manifest,
   verify every object, and restore into empty tables using the Parquet recovery
   procedure.
6. Run migration parity, referential-integrity, financial reconciliation, and
   role acceptance suites.
7. Switch traffic only after two-person approval.

Record recovery-point and recovery-time results, lost/replayed transactions,
customer impact, and follow-up actions.
