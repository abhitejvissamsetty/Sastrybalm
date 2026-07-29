# ── Stage 1: Build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS builder

WORKDIR /build

# Install build-time system deps for PyMySQL (pure-python, so minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.lock .
RUN pip install --no-cache-dir --prefix=/install -r requirements.lock


# ── Stage 2: Production image ───────────────────────────────────────────────
FROM python:3.12-slim@sha256:57cd7c3a7a273101a6485ba99423ee568157882804b1124b4dd04266317710de AS production

# Labels
LABEL maintainer="Safar <admin@safar.com>"
LABEL description="Safar SFA — FastAPI backend & admin dashboard"

# Non-root user for security
RUN groupadd -r safar && useradd -r -g safar -d /app -s /sbin/nologin safar

WORKDIR /app

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY run.py .
COPY alembic.ini .
COPY gunicorn.conf.py .
COPY migrations ./migrations
COPY scripts ./scripts
COPY entrypoint.sh .
COPY app/ ./app/

# Create uploads directory and set ownership
RUN mkdir -p /app/app/static/uploads && \
    chown -R safar:safar /app

# Switch to non-root user
USER safar

# Expose the application port
EXPOSE 8090

# Health-check remains available when production API documentation is disabled.
HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/health/live')" || exit 1

# Entrypoint: run migrations ONCE, then start Gunicorn (no per-worker deadlocks)
ENTRYPOINT ["bash", "/app/entrypoint.sh"]
