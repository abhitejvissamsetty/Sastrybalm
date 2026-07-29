# Final release verification — 2026-07-29

This report records the final local production-equivalent verification. An
open checklist item remains open when it requires deployed credentials,
third-party delivery evidence, hosted CI, a human sign-off, or an independent
review that cannot be produced by the application repository.

## Passed gates

- Exact production image built as `sastrybalm-audit:2026-07-29`.
- Backend: 101 application tests passed with 47.23% coverage; the configured
  40% release threshold passed. After adding the fail-closed external-gate
  tests, the complete suite passed 104 tests.
- Mobile: `flutter analyze` returned zero diagnostics; 30 tests passed. The
  five isolated backend-connected mobile E2E tests also passed in their
  dedicated deterministic run.
- Correctness lint: Flake8 `E9,F63,F7,F82` gate passed.
- Static security: Bandit reported no high-severity finding.
- Dependencies: `pip-audit` reported no known vulnerability after upgrading
  Jinja2 and python-dotenv and replacing python-jose/ecdsa with PyJWT 2.13.0.
- Image: Trivy reported 0 high and 0 critical vulnerabilities.
- Secrets: Gitleaks scanned 50 commits and found no leak.
- Migrations: live MySQL reported Alembic revision `c7f4a1b83d20 (head)`;
  `alembic check` reported no new upgrade operation.
- Deployment: the effective production Compose configuration passed private
  service, TLS edge, secure-cookie, docs, and source-mount invariants.
- Backup/storage safety tests, encrypted SQL restore, signed Parquet clean-DB
  recovery, migration recovery, outbound webhook signing, deterministic
  fixtures, authorization, workflow transitions, query budgets, runbooks, and
  observability unit/contract tests are included in the passing backend suite.
- Performance: 400 requests at concurrency 20 against 2,000 outlets and 5,000
  orders passed all 10 budgets with 0% errors, 294.83 ms p95, 151.01 requests/s,
  35.92% average CPU, 631.69 MB peak memory, 1.59 ms database latency, and
  3.97% database connection utilization.

## Open external gates

1. **Deployed credential rotation** — runtime defaults are rejected and the
   history leak scan passes, but the owners of the deployed database, admin,
   JWT, webhook, SMTP, and S3 accounts must rotate and record
   their credentials using the credential-rotation runbook.
2. **Webhook secret rotation** — mandatory timestamp-bound outbound signatures
   and strong-secret validation pass. Each receiver still requires coordinated
   deployment of its independently rotated secret.
3. **S3 configuration and live workflow** — current readiness reports object
   storage unavailable. Valid least-privilege permanent/temporary credentials,
   region, endpoint, and bucket policy are required before live upload,
   download, presigned-expiry, deletion, and tenant-isolation evidence can be
   captured.
4. **Central telemetry delivery** — structured redacted logs, protected
   multiprocess metrics, Sentry integration/tracing, alert rules, and local
   tests pass. A real Sentry event/trace and acknowledged test alert from the
   production receivers must be recorded.
5. **Hosted CI** — all workflow stages are wired and their local equivalents
   pass, but the current uncommitted working tree has not run in GitHub
   Actions. A successful workflow URL/artifact set is required.
6. **Role-by-role UAT** — requires named business users and signed results.
7. **Independent security review** — must be performed by a reviewer
   independent of the implementation and all critical/high findings remediated.
8. **Final 10/10 production re-audit** — can only be closed after gates 1–7
   above pass against the deployed production-equivalent release.

## Closing the external gates

1. Copy `docs/release-evidence.example.json` to
   `docs/release-evidence.json`. Do not put credentials in this file.
2. Populate all change IDs, HTTPS evidence links, artifact names, signers,
   timestamps, and report hashes.
3. Run
   `python scripts/verify_external_release_evidence.py docs/release-evidence.json`.
4. Configure the S3 secrets named in
   `.github/workflows/external-release-gates.yml`. The `S3_DENIED_*` identity
   must belong to another tenant/account or have an explicit deny for the
   production bucket.
5. Run the **External release gates** workflow. Retain both uploaded artifacts
   and record its successful GitHub Actions URL in the release record.
6. Run the manually dispatchable main **CI** workflow against the same release
   commit. The commit must match `release_commit` in the evidence manifest.

The external-gate implementation itself passed 37 focused security,
observability, runbook, and evidence-validation tests. Both GitHub workflows
pass Actionlint. The incomplete example evidence and an invocation without S3
credentials were also verified to fail closed.

## Current readiness evidence

The local readiness endpoint returned database, migrations, and scheduler as
healthy, while object storage and SMTP were not ready. This is expected to
remain a deployment blocker rather than being waived.
