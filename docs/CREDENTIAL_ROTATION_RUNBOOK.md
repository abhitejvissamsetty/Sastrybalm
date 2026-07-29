# Credential-rotation runbook

Never place credential values in Git, tickets, chat, shell history, command
output, logs, images, or runbook evidence. Generate values in the approved
secret manager and record only secret version identifiers and timestamps.
Require two-person review.

## Rotation order

1. S3 temporary and permanent access keys (independent principals)
2. Outbound webhook signing secrets
3. SMTP credential
4. Database application and root credentials
5. Administrator password
6. Backup encryption key using decrypt-old/re-encrypt-new migration
7. Metrics scrape token and Sentry DSN credential
8. Application session secret/JWT signing secret

Each credential must be unique, meet production minimum length, and have only
the permissions needed by its one purpose.

## Standard procedure

1. Inventory consumers and choose a rollback version.
2. Create a new credential without disabling the old version.
3. Update the secret manager and one canary consumer.
4. Verify authentication, authorization boundaries, audit event, monitoring,
   and negative tests with the old/invalid value.
5. Roll out all consumers.
6. Revoke the old credential and prove it fails.
7. Search logs/history/artifacts for accidental disclosure.
8. Record issuer, consumer, secret version, activation/revocation timestamps,
   verification evidence, and next rotation date.

## Special cases

- **Webhook:** coordinate secret rotation with each receiver, canary a
  timestamp-bound signature, then prove the retired key fails.
- **Database:** create/alter the least-privilege application account, canary new
  connections, drain old pools, revoke old password, and confirm root is not
  used by application containers.
- **JWT/session secret:** deploy during maintenance, increment every active
  user's token version, clear server sessions, and require reauthentication.
- **Backup key:** retain the old version offline until every retained encrypted
  backup is re-encrypted and restore-tested. Never discard a key based only on
  successful encryption.
- **S3:** prove each principal cannot access the other bucket/prefix and that
  public access remains blocked before revoking old keys.

Emergency rotation follows the incident-response runbook and prioritizes
revocation/containment over overlap.
