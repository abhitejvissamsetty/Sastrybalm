#!/bin/bash
set -e

echo "=== Safar Entrypoint ==="

# ── Step 0: Wait for MySQL TCP port to be reachable ────────────────────────
DB_HOST="${DB_HOST:-db}"
DB_PORT="${DB_PORT:-3306}"
echo "Waiting for MySQL at ${DB_HOST}:${DB_PORT}..."
for i in $(seq 1 60); do
    if timeout 1 bash -c "echo > /dev/tcp/${DB_HOST}/${DB_PORT}" 2>/dev/null; then
        echo "MySQL port is reachable."
        break
    fi
    echo "[${i}/60] MySQL not yet reachable, retrying in 2s..."
    sleep 2
done

# A scheduler container waits for the web container to migrate and become
# healthy, then runs only background jobs.
if [ "${1:-}" = "scheduler" ]; then
    echo "Starting dedicated scheduler..."
    exec python -m app.scheduler_runner
fi

# ── Step 1: Run versioned migrations ONCE before Gunicorn workers fork ──────
echo "Running database migrations (pre-fork, single process)..."
alembic upgrade head
echo "Database migrations completed."

# ── Step 2: Launch Gunicorn with Uvicorn workers ────────────────────────────
PROMETHEUS_MULTIPROC_DIR="${PROMETHEUS_MULTIPROC_DIR:-/tmp/prometheus}"
export PROMETHEUS_MULTIPROC_DIR
mkdir -p "${PROMETHEUS_MULTIPROC_DIR}"
find "${PROMETHEUS_MULTIPROC_DIR}" -mindepth 1 -maxdepth 1 -type f -delete
echo "Starting Gunicorn..."
exec gunicorn \
    --config /app/gunicorn.conf.py \
    --bind 0.0.0.0:8090 \
    --workers 4 \
    --timeout 120 \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    app.main:app
