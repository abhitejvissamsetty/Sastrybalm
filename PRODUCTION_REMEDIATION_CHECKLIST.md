# Safar SFA Production Remediation Checklist

An item is struck through only after its implementation and verification gate passes.
Latest verification evidence and explicit external blockers are recorded in
[`docs/FINAL_RELEASE_VERIFICATION_2026-07-29.md`](docs/FINAL_RELEASE_VERIFICATION_2026-07-29.md).

## P0 — Critical security and data isolation

- [x] ~~Eliminate OTP disclosure across mobile and web, hash newly issued OTPs, invalidate legacy plaintext OTPs, enforce request throttling, expiry, and verification-attempt lockout, and add regression tests.~~
- [ ] Remove known/default application, database, administrator, JWT, webhook, SMTP, and storage credentials from runtime configuration; rotate deployed credentials and add leak scanning.
- [x] ~~Make production startup fail unless strong secrets, secure cookies, trusted CORS origins, and required SMTP credentials are supplied.~~
- [x] ~~Introduce one centralized object-access service for geography, position hierarchy, outlet, warehouse, vendor, and ownership authorization.~~
- [x] ~~Apply object-level authorization to every read and mutation route, including direct identifier lookups.~~
- [x] ~~Add cross-territory, cross-vendor, cross-user, and horizontal-privilege-escalation tests.~~
- [x] ~~Remove the duplicate debug login endpoint and credential/token response logging.~~
- [x] ~~Remove the retired inbound integration webhook surface and require timestamp-bound HMAC signatures and strong secrets for every remaining outbound webhook.~~

## P0 — Runtime and deployment safety

- [x] ~~Move APScheduler out of Gunicorn workers into exactly one dedicated scheduler process and verify single ownership.~~
- [x] ~~Add scheduler job idempotency, database locking, duplicate-notification protection, and failure monitoring.~~
- [x] ~~Enable HTTPS termination, HTTP-to-HTTPS redirects, TLS certificate management, secure cookies, HSTS, CSP, and remaining required browser security headers.~~
- [x] ~~Keep MySQL, Adminer, and the direct application port private in every deployment configuration; disable or remove Adminer in production.~~
- [x] ~~Disable public API documentation in production or protect it with administrator authentication.~~
- [x] ~~Add production health/readiness checks for database queries, object storage, SMTP, migrations, and scheduler ownership.~~

## P0 — Database migrations and recovery

- [x] ~~Replace `db_migrate.py` schema mutation with ordered, versioned Alembic revisions.~~
- [x] ~~Create a real baseline revision and forward revisions for every current model/schema change.~~
- [x] ~~Remove broad migration exception swallowing and all well-known root-password probing.~~
- [x] ~~Make application startup fail when its migration command fails.~~
- [x] ~~Test clean installation, upgrade from the last release, downgrade policy, interrupted migration recovery, and schema/ORM parity.~~
- [x] ~~Remove sensitive legacy backups from application-served directories after retaining a verified encrypted recovery copy.~~

## P0 — Object storage and backup recovery

- [ ] Correct permanent and temporary S3 bucket credentials, endpoints, regions, and bucket policies.
- [ ] Verify authenticated upload, download, presigned URL expiry, deletion policy, and access isolation.
- [x] ~~Verify image/document workflows do not silently depend on ephemeral local fallback in production.~~
- [x] ~~Prove SQL backup creation, encrypted storage, retention, download, and restore into a clean database.~~
- [x] ~~Prove Parquet rolling backup creation, retention, integrity, and recovery procedure.~~
- [x] ~~Add automated backup/restore tests and record a disaster-recovery drill.~~

## P1 — Deterministic acceptance environment

- [x] ~~Build deterministic factories and fixtures for Admin, L4, L3, L2, L1, Vendor Admin, Vendor Technician, and QC Manager.~~
- [x] ~~Seed multiple zones, regions, territories, reporting trees, warehouses, products, vendors, channel partners, beats, and outlets.~~
- [x] ~~Seed realistic orders, visits, payments, expenses, leaves, timesheets, material requests, procurement records, assets, and maintenance records.~~
- [x] ~~Provide isolated test databases with repeatable setup/teardown and no dependency on live services.~~

## P1 — Backend correctness suite

- [x] ~~Replace broken `scratch` and `exclude_from_deployment` tests with an actively maintained `tests/` suite.~~
- [x] ~~Test authentication, session/JWT expiry, revocation, OTP abuse, and inactive users.~~
- [x] ~~Test primary and secondary order totals, payment states, inventory locking, deductions, insufficient stock, and duplicate submission.~~
- [x] ~~Test visit requirements, GPS rules, no-order flow, joint working, attendance, timesheets, expenses, and leaves.~~
- [x] ~~Test every approval/rejection transition and reporting-hierarchy rule.~~
- [x] ~~Test the complete material-request, recce, quotation, work-order, QC, procurement-item, deployment, capitalization, and maintenance lifecycle.~~
- [x] ~~Test mandatory outbound webhook signing and removal of every retired integration route.~~
- [x] ~~Add coverage reporting and enforce release thresholds in CI.~~

## P1 — Mobile reliability suite

- [x] ~~Resolve Flutter analyzer diagnostics, especially asynchronous `BuildContext` usage and ignored failures.~~
- [x] ~~Add tests for navigation and permissions for every mobile role.~~
- [x] ~~Add tests for login, OTP, logout, session expiry, and inactive/checked-out users.~~
- [x] ~~Add tests for GPS denied, unavailable, spoofed, stale, and out-of-range states.~~
- [x] ~~Add tests for camera/gallery denial, invalid images, upload failure, retry, and replacement.~~
- [x] ~~Add tests for offline queue ordering, retry backoff, dead-letter handling, encryption, and conflict resolution.~~
- [x] ~~Add server-enforced idempotency keys and tests for duplicate MR, asset, order, payment, visit, and procurement submissions.~~
- [x] ~~Add end-to-end tests against the deterministic backend environment.~~

## P1 — Performance, observability, and operations

- [x] ~~Add pagination and bounded queries to every list/history endpoint.~~
- [x] ~~Remove confirmed N+1 query patterns and add query-count regression tests.~~
- [x] ~~Load-test realistic hierarchies, thousands of outlets/orders, image traffic, and concurrent mobile synchronization.~~
- [x] ~~Define and enforce latency, error-rate, throughput, database, CPU, and memory release budgets.~~
- [ ] Add structured logs with secret/PII redaction, centralized error reporting, metrics, tracing, and alerting.
- [x] ~~Add audit trails for security-sensitive reads, mutations, approvals, exports, and configuration changes.~~
- [x] ~~Pin all container and application dependencies, scan images/dependencies, and set container resource limits.~~

## Final release gate

- [ ] Run the complete backend, mobile, security, migration, storage, backup/restore, and performance suites in CI.
- [ ] Complete role-by-role user acceptance testing with signed results.
- [ ] Perform an independent security review and remediate all critical/high findings.
- [x] ~~Complete deployment, rollback, incident-response, credential-rotation, and disaster-recovery runbooks.~~
- [ ] Re-audit the production-equivalent release and achieve all measurable 10/10 release gates.
