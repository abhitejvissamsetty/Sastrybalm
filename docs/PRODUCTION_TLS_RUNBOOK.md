# Production TLS certificate runbook

The production Compose override publishes only Nginx on TCP 80/443. Nginx
redirects every HTTP request to HTTPS and reads these files from
`TLS_CERT_DIR`:

- `fullchain.pem`
- `privkey.pem`

Use certificates issued for the deployed hostname by the organization's
certificate authority or an ACME client. Keep the private key readable only by
the deployment account and never commit either file.

Before deployment:

1. Set `TLS_CERT_DIR` to the absolute certificate directory.
2. Run `python scripts/verify_production_compose.py`.
3. Run `nginx -t` against `nginx/production.conf` with the certificate
   directory mounted at `/etc/nginx/certs`.
4. Start with both Compose files and verify HTTP returns `308`, HTTPS succeeds,
   `/api/docs` returns `404`, and the HSTS/CSP/security headers are present.

Renew certificates before expiry using the issuer's automated renewal job.
After renewal, validate the files and reload Nginx (`nginx -s reload`). Monitor
certificate expiry and alert at 30, 14, and 7 days. Roll back by restoring the
previous certificate pair and reloading Nginx; never disable HTTPS as a
rollback.
