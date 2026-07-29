# Performance Release Gate

The release gate is defined by `performance/budgets.json` and executed by
`python -m performance.release_gate`. CI seeds a deterministic base hierarchy,
starts four application workers, creates uniquely tagged high-volume records,
and exercises paginated outlet synchronization, order synchronization,
hierarchy traversal, and image traffic concurrently.

The harness always deletes its tagged order items, orders, and outlets in
dependency order. A release fails if cleanup cannot complete, any request
fails, or any latency, throughput, database, CPU, or memory budget is exceeded.
The JSON report is uploaded from CI as `performance-release-report`.

## Verified baseline — 2026-07-29

- Dataset: 2,000 outlets and 5,000 orders
- Requests: 400 at concurrency 20
- HTTP p95: 294.83 ms
- Image p95: 232.32 ms
- Throughput: 151.01 requests/second
- Error rate: 0%
- Representative database query: 1.59 ms
- Database connection utilization: 3.97%
- Average allocated CPU: 35.92%
- Peak memory: 631.69 MB
- Result: all ten enforced checks passed
- Cleanup proof: zero `PERF%-OUT-%` outlets and zero `PERF%-ORD-%` orders
  remained after the run

Budgets must only be changed through review with a written capacity rationale.
Increasing a limit merely to make a failing release pass is prohibited.
