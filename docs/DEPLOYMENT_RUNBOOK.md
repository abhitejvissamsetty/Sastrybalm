# Production deployment runbook

## Required evidence before deployment

- Approved immutable image digest with zero unresolved critical/high findings
- Green backend, mobile, E2E, migration, storage, restore, and performance jobs
- Signed role-by-role UAT and independent security-review disposition
- Successful production-equivalent S3, SMTP, outbound webhook, Sentry, metrics,
  alert-routing, scheduler, backup, and restore checks
- Change ticket containing operator, reviewer, release SHA, image digest,
  database backup identifier, planned window, and rollback owner

## Preflight

1. Freeze mutations and announce the change window.
2. Confirm current alerts are clear and record baseline latency/error metrics.
3. Create and download-verify an encrypted SQL backup.
4. Confirm the latest signed Parquet manifest passes full download verification.
5. Render the effective configuration:

   ```sh
   docker compose -f docker-compose.yml -f docker-compose.production.yml config
   python scripts/verify_production_compose.py
   ```

6. Confirm MySQL/Adminer/direct app ports are absent, secrets are supplied by the
   approved secret manager, and the release references immutable digests.

## Deploy

1. Pull the approved digest; never rebuild on the production host.
2. Start database and the one-shot migration/startup process. `entrypoint.sh`
   must terminate on any Alembic failure.
3. Confirm `alembic current` equals the reviewed head.
4. Start the application, then exactly one scheduler, then Nginx.
5. Require `/health/live` HTTP 200 and `/health/ready` HTTP 200.
6. Confirm the protected multiprocess metrics endpoint exposes HTTP, latency,
   database-pool, scheduler-owner, process, and runtime metrics.
7. Run authenticated smoke checks for every role, one read and one reversible
   mutation, outbound webhook signature verification, upload/download, and alert
   delivery.
8. Remove maintenance mode only after the reviewer signs the evidence.

## Post-deploy

Monitor for at least 30 minutes: p95 latency, 5xx/4xx changes, worker restarts,
database connections/slow queries, memory/CPU, scheduler ownership, failed
jobs, Sentry events, S3 failures, SMTP failures, and mobile dead letters.
Attach logs and dashboards to the change ticket. Do not declare success while
any required readiness check is degraded.
