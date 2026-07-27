#!/bin/bash
set -e

echo "=== Sastrybalm Entrypoint ==="

# ── Step 1: Run database migrations ONCE before Gunicorn workers fork ──
echo "Running database migrations (pre-fork, single process)..."
python db_migrate.py
echo "Database migrations completed."

# ── Step 2: Launch Gunicorn with Uvicorn workers ──
echo "Starting Gunicorn..."
exec gunicorn \
    --bind 0.0.0.0:8090 \
    --workers 4 \
    --timeout 120 \
    --worker-class uvicorn.workers.UvicornWorker \
    --access-logfile - \
    --error-logfile - \
    app.main:app
