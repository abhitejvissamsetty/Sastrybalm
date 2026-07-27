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

# ── Step 1: Run database migrations ONCE before Gunicorn workers fork ──────
echo "Running database migrations (pre-fork, single process)..."
python db_migrate.py || {
    echo "WARNING: db_migrate.py failed, but proceeding to start app..."
}
echo "Database migrations completed."

# ── Step 2: Launch Gunicorn with Uvicorn workers ────────────────────────────
echo "Starting Gunicorn..."
exec gunicorn \
    --bind 0.0.0.0:8090 \
    --workers 4 \
    --timeout 120 \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    app.main:app
