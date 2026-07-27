# Safar SFA — Deployment & Operations Guide

This guide covers deployment and local execution options for the **Safar SFA** FastAPI application.

---

## 1. Quick Start — Local Development

### Prerequisites
- Python 3.9+ installed
- MySQL Database running locally (e.g. MAMP on port `8889` or Docker MySQL on port `3308`)

### Setup & Run
```bash
# 1. Clone the repository and enter directory
cd Safar

# 2. Configure environment variables (.env)
cp .env.example .env
# Ensure DB_PORT, DB_USER, DB_PASSWORD, DB_NAME match your MySQL instance

# 3. Run database migrations & seed initial data
python3 db_migrate.py

# 4. Start the application server
./start_safar.sh
# OR manually run:
python3 run.py
```

The application will be accessible at:
- **Web App / Admin Portal**: [http://localhost:8090](http://localhost:8090)
- **Login Page**: [http://localhost:8090/login](http://localhost:8090/login)
- **Interactive API Docs**: [http://localhost:8090/api/docs](http://localhost:8090/api/docs)

---

## 2. Option 1: Docker Compose (Recommended for Production)

### Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Host Machine                                               │
│                                                             │
│  ┌───────────────┐    ┌─────────────────┐    ┌───────────┐  │
│  │     Nginx     │───▶│   FastAPI App   │───▶│   MySQL   │  │
│  │  :8080 / :443 │    │      :8090      │    │   :3306   │  │
│  └───────────────┘    └─────────────────┘    └───────────┘  │
│                                                             │
│   ── safar-net (bridge network) ────────────────────  │
└─────────────────────────────────────────────────────────────┘
```

Containers orchestrated via `docker-compose.yml`:
- **`db`** — MySQL 8.0 with persistent data volume and health checks.
- **`app`** — Python container running FastAPI with Gunicorn + Uvicorn workers. Auto-runs `db_migrate.py` on container start.
- **`nginx`** — Alpine Nginx reverse proxy forwarding public traffic.
- **`adminer`** — Web-based Database Manager available at `http://localhost:8081`.

### Build & Deploy Commands
```bash
# Build and start all services in detached mode
docker compose up -d --build

# Verify container statuses
docker compose ps

# View application logs
docker compose logs -f app
```

---

## 3. Option 2: VPS / Systemd Manual Deployment

### Step 1: Clone & Virtual Environment
```bash
cd /var/www/safar
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn uvicorn
```

### Step 2: Database Migration
```bash
python3 db_migrate.py
```

### Step 3: Configure Systemd Service
Create `/etc/systemd/system/safar.service`:

```ini
[Unit]
Description=Safar SFA FastAPI Daemon
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/safar
ExecStart=/var/www/safar/venv/bin/gunicorn \
          --workers 4 \
          --worker-class uvicorn.workers.UvicornWorker \
          --bind 127.0.0.1:8090 \
          app.main:app

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo systemctl daemon-reload
sudo systemctl start safar
sudo systemctl enable safar
```

---

## 4. Environment Variables Reference (`.env`)

| Key | Example Value | Description |
|---|---|---|
| `APP_NAME` | `Safar SFA` | Application Display Name |
| `SECRET_KEY` | *(random long string)* | JWT Signing & Session Secret |
| `DB_HOST` | `127.0.0.1` | MySQL Host IP |
| `DB_PORT` | `8889` (MAMP) / `3308` (Docker) | MySQL Server Port |
| `DB_USER` | `safar_user` | MySQL Database Username |
| `DB_PASSWORD` | `safar_password` | MySQL Database Password |
| `DB_NAME` | `safar_db` | MySQL Database Name |
| `ADMIN_USERNAME` | `admin` | Admin Portal Username |
| `ADMIN_PASSWORD` | `admin123` | Admin Portal Password |
| `JWT_EXPIRE_MINUTES` | `10080` | Token Expiration (7 days) |

---

## 5. Maintenance & Troubleshooting Commands

```bash
# Check if port 8090 is in use
lsof -i :8090

# Stop server process running on 8090
kill -9 $(lsof -ti:8090)

# Check database connection manually
python3 db_migrate.py

# Restart app using startup script
./start_safar.sh
```
