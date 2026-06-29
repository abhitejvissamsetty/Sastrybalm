# Sastrybalm SFA — Deployment Guide

This guide covers two deployment methods for the **Sastrybalm SFA** FastAPI application:

1. **[Docker Compose (Recommended)](#option-1-docker-compose)** — Fully containerized, portable, one-command deploy.
2. **[CloudPanel VPS (Manual)](#option-2-cloudpanel-vps)** — Traditional systemd + reverse-proxy deployment.

---

## Option 1: Docker Compose

### Architecture

```
┌──────────────────────────────────────────────────────┐
│  Host Machine                                        │
│                                                      │
│  ┌───────────┐    ┌───────────────┐    ┌──────────┐  │
│  │   Nginx   │───▶│  FastAPI App  │───▶│  MySQL   │  │
│  │  :80/:443 │    │     :8002     │    │  :3306   │  │
│  └───────────┘    └───────────────┘    └──────────┘  │
│                                                      │
│   ── sastrybalm-net (bridge) ──────────────────────  │
└──────────────────────────────────────────────────────┘
```

Three containers orchestrated via Docker Compose:
- **`db`** — MySQL 8.0 with persistent volume and health checks.
- **`app`** — Python 3.12 slim image running Gunicorn + Uvicorn workers. Auto-runs `db_migrate.py` on startup.
- **`nginx`** — Alpine Nginx reverse proxy forwarding traffic to the app.

### Prerequisites

- Docker Engine ≥ 24.x and Docker Compose ≥ 2.x installed on your server.
- A domain name pointed to your server's IP (for SSL).

### Quick Start

```bash
# 1. Clone the repository
git clone <your-repo-url> && cd Sastrybalm

# 2. Create your production .env from the template
cp .env.example .env
# Edit .env and set real values (SECRET_KEY, DB_PASSWORD, etc.)

# 3. Build and launch all services
docker compose up -d --build

# 4. Verify everything is running
docker compose ps
```

The application will be available at `http://<your-server-ip>`.

### File Overview

| File | Purpose |
|---|---|
| `Dockerfile` | Multi-stage build: installs deps, copies app code, runs Gunicorn |
| `docker-compose.yml` | Orchestrates MySQL, FastAPI app, and Nginx services |
| `.dockerignore` | Excludes `mobile/`, `venv/`, docs, etc. from the build context |
| `nginx/default.conf` | Nginx reverse proxy configuration |
| `.env.example` | Template for environment variables |

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `SECRET_KEY` | *(must change)* | App secret for JWT signing and sessions |
| `MYSQL_ROOT_PASSWORD` | `rootpassword` | MySQL root password |
| `DB_USER` | `sastrybalm_user` | Application database user |
| `DB_PASSWORD` | `sastrybalm_password` | Application database password |
| `DB_NAME` | `sastrybalm_db` | Database name |
| `JWT_EXPIRE_MINUTES` | `10080` | JWT token expiry (7 days) |
| `SMTP_*` | *(empty)* | Email configuration (optional) |
| `CMMS_*` / `CONNECT_*` | *(empty)* | External API integrations |

### Enabling HTTPS / SSL

1. Place your SSL certificate files in `nginx/certs/`:
   ```
   nginx/certs/fullchain.pem
   nginx/certs/privkey.pem
   ```
2. Edit `nginx/default.conf`:
   - Uncomment the `return 301 https://...` line in the HTTP server block.
   - Uncomment the entire HTTPS server block at the bottom.
   - Set `server_name` to your actual domain.
3. Restart Nginx:
   ```bash
   docker compose restart nginx
   ```

### Common Commands

```bash
# View logs (follow mode)
docker compose logs -f app

# Rebuild only the app after code changes
docker compose up -d --build app

# Stop everything
docker compose down

# Stop and destroy all data (including database)
docker compose down -v

# Enter the running app container
docker compose exec app bash

# Access MySQL CLI
docker compose exec db mysql -u sastrybalm_user -p sastrybalm_db
```

### Database Backups

```bash
# Dump the database
docker compose exec db mysqldump -u root -p${MYSQL_ROOT_PASSWORD} sastrybalm_db > backup_$(date +%Y%m%d).sql

# Restore from backup
docker compose exec -T db mysql -u root -p${MYSQL_ROOT_PASSWORD} sastrybalm_db < backup_20250101.sql
```

---

## Option 2: CloudPanel VPS

### Prerequisites

1. A VPS with **CloudPanel** installed.
2. A domain name pointed to your VPS IP address (e.g., `api.sastrybalm.com`).
3. SSH access to your VPS with `root` or a sudo user.

### Step 1: Create a Database in CloudPanel

1. Log in to your CloudPanel admin dashboard.
2. Go to **Databases** → **Add Database**.
3. Fill in the details:
   - **Database Name**: `sastrybalm_db`
   - **Database User**: `sastrybalm_user`
   - **Password**: *Generate a secure password and save it*
4. Click **Add Database**.

### Step 2: Create a Reverse Proxy Site

1. In CloudPanel, go to **Sites** → **Add Site** → **Create a Reverse Proxy Site**.
2. Fill in:
   - **Domain Name**: `api.sastrybalm.com`
   - **Site User**: `clp-user`
   - **Reverse Proxy Port**: `8002`
3. Click **Create Site**.
4. Go to **SSL/TLS** tab → **New Let's Encrypt Certificate**.

### Step 3: Clone Code and Prepare

```bash
# SSH into VPS and navigate to the site directory
cd /home/clp-user/htdocs/api.sastrybalm.com
rm -rf *

# Clone/copy project files here
# Ensure run.py, alembic.ini, and the app/ folder are at the root
chown -R clp-user:clp-user /home/clp-user/htdocs/api.sastrybalm.com
```

### Step 4: Setup Python Virtual Environment

```bash
sudo su - clp-user
cd /home/clp-user/htdocs/api.sastrybalm.com

python3 -m venv venv
source venv/bin/activate

pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

> [!NOTE]
> If building native wheels fails, install system headers as `root`:
> `apt-get install python3-dev default-libmysqlclient-dev build-essential`

### Step 5: Environment Variables

Create `.env` at `/home/clp-user/htdocs/api.sastrybalm.com/.env`:

```env
APP_NAME="Sastrybalm SFA"
SECRET_KEY="your-random-generated-long-secret-key"

DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=sastrybalm_user
DB_PASSWORD=your_created_db_password
DB_NAME=sastrybalm_db

JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=10080
```

### Step 6: Run Migrations

```bash
alembic upgrade head
```

### Step 7: Configure Systemd Service

As **`root`**, create `/etc/systemd/system/sastrybalm.service`:

```ini
[Unit]
Description=Sastrybalm FastAPI Daemon
After=network.target

[Service]
User=clp-user
Group=clp-user
WorkingDirectory=/home/clp-user/htdocs/api.sastrybalm.com
ExecStart=/home/clp-user/htdocs/api.sastrybalm.com/venv/bin/gunicorn \
          --workers 4 \
          --worker-class uvicorn.workers.UvicornWorker \
          --bind 127.0.0.1:8002 \
          app.main:app

[Install]
WantedBy=multi-user.target
```

```bash
systemctl daemon-reload
systemctl start sastrybalm
systemctl enable sastrybalm
systemctl status sastrybalm
```

### Step 8: Nginx Static Files (Optional)

In the CloudPanel **Vhost** tab, add above the main location block:

```nginx
location /static/ {
    alias /home/clp-user/htdocs/api.sastrybalm.com/app/static/;
    expires 30d;
    access_log off;
}
```

---

## Troubleshooting

| Issue | Command |
|---|---|
| **Docker: App logs** | `docker compose logs -f app` |
| **Docker: DB health** | `docker compose exec db mysqladmin ping -h localhost -u root -p` |
| **Systemd: App logs** | `journalctl -u sastrybalm.service -f` |
| **Verify local connection** | `curl -I http://127.0.0.1:8002` |
| **Permission errors** | `chown -R clp-user:clp-user /home/clp-user/htdocs/...` |
