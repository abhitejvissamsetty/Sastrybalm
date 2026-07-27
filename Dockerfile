# ── Stage 1: Build dependencies ──────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build-time system deps for PyMySQL (pure-python, so minimal)
RUN apt-get update && \
    apt-get install -y --no-install-recommends gcc && \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Production image ───────────────────────────────────────────────
FROM python:3.12-slim AS production

# Labels
LABEL maintainer="Sastrybalm <admin@sastrybalm.com>"
LABEL description="Sastrybalm SFA — FastAPI backend & admin dashboard"

# Non-root user for security
RUN groupadd -r sastrybalm && useradd -r -g sastrybalm -d /app -s /sbin/nologin sastrybalm

WORKDIR /app

# Copy pre-built Python packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY alembic.ini .
COPY run.py .
COPY db_migrate.py .
COPY app/ ./app/
COPY migrations/ ./migrations/

# Create uploads directory and set ownership
RUN mkdir -p /app/app/static/uploads && \
    chown -R sastrybalm:sastrybalm /app

# Switch to non-root user
USER sastrybalm

# Expose the application port
EXPOSE 8090

# Health-check: hit the docs endpoint
HEALTHCHECK --interval=30s --timeout=5s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8090/api/docs')" || exit 1

# Default: Gunicorn with Uvicorn workers for production
CMD ["gunicorn", \
     "--bind", "0.0.0.0:8090", \
     "--workers", "4", \
     "--worker-class", "uvicorn.workers.UvicornWorker", \
     "--access-logfile", "-", \
     "--error-logfile", "-", \
     "app.main:app"]
