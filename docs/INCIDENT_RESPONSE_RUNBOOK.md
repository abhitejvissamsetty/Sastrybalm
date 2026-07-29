# Incident-response runbook

## Severity and command

- **SEV-1:** confirmed compromise, material data loss/corruption, total outage,
  or unauthorized financial/inventory mutation
- **SEV-2:** major role/integration failure, sustained release-budget breach,
  backup/scheduler failure, or partial outage
- **SEV-3:** contained degradation with a workaround

Assign an incident commander, operations lead, security lead, communications
lead, and scribe. Use an out-of-band channel if application credentials may be
compromised. Preserve an immutable timeline.

## First 15 minutes

1. Acknowledge the alert and open an incident identifier.
2. Determine affected environment, roles, tenants/geographies, data classes,
   integrations, and first known bad timestamp.
3. Contain: maintenance mode, stop scheduler/writers where necessary, revoke
   sessions by incrementing token versions, and disable compromised webhook or
   integration credentials.
4. Preserve structured logs, audit events, Sentry event/trace identifiers,
   database logs, object-store access logs, container metadata, and current
   image/configuration digests. Never copy plaintext secrets into the timeline.
5. Notify required internal/legal/privacy stakeholders under applicable policy.

## Investigation and recovery

- Authentication incident: rotate affected secrets, invalidate OTP/session/JWT
  state, inspect audit events and horizontal-scope denials.
- Data incident: stop writes, capture forensic backup, reconcile financial and
  inventory transitions, restore only into a clean environment.
- S3 incident: revoke keys, block public access, inspect object access/version
  logs, validate signed manifests and object hashes.
- Scheduler incident: retain one owner, revoke duplicate processes, reconcile
  notifications/jobs through idempotency records.
- Webhook incident: rotate the independent webhook secret, reject old
  signatures, inspect replay/event records and downstream mutations.

Recovery requires green readiness, security, reconciliation, role smoke, and
alert tests. Maintain enhanced monitoring for 24 hours.

## Closure

Within five business days publish a blameless review: root cause, control
failure, complete timeline, impact, recovery evidence, detection gap, and
owned/due-dated corrective actions. Rotate any credential exposed to responders
or logs.
