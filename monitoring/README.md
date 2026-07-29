# Monitoring and alert routing

Scrape `GET /metrics` only through the private service network. Authenticate
with either `Authorization: Bearer $METRICS_TOKEN` or the legacy
`X-Metrics-Token` header. Never publish the endpoint or token.

Load `alerts.yml` into the production Prometheus-compatible monitoring
platform. Route `critical` alerts to the 24×7 incident receiver and `warning`
alerts to the service operations receiver. Each receiver must have a tested
primary and secondary contact; production deployment is blocked until a test
alert is acknowledged and its incident identifier is recorded.

Sentry is the centralized error and trace backend. Production startup requires
an HTTPS DSN, disables default PII, removes request bodies/cookies/query values,
and samples traces using `SENTRY_TRACES_SAMPLE_RATE`.

Quarterly verification:

1. Trigger a synthetic 500 response in the non-production production-equivalent
   environment and confirm a redacted Sentry event and trace.
2. Trigger the test alert and confirm both escalation contacts receive it.
3. Query each rule and confirm its metric exists.
4. Rotate the metrics token and Sentry DSN credential using the credential
   rotation runbook.
