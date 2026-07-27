# Safar SFA: VPS Deployment Guide

This guide outlines the steps to deploy the Safar SFA platform to a Linux VPS (Ubuntu 22.04+ recommended).

## 1. Prerequisites
- A VPS with at least 2GB RAM.
- A domain name pointing to your VPS IP.
- SSH access to the server.

## 2. Server Preparation

Update the system and install essential dependencies:
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3.11 python3.11-venv python3-pip mysql-server nginx git curl lsof
```

## 3. Database Setup (MySQL)

Secure your MySQL installation and create the production database:
```bash
sudo mysql_secure_installation
```

Log in to MySQL:
```bash
sudo mysql -u root -p
```

Run the following SQL commands:
```sql
CREATE DATABASE safar_db CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'safar_admin'@'localhost' IDENTIFIED BY 'STRONG_PASSWORD_HERE';
GRANT ALL PRIVILEGES ON safar_db.* TO 'safar_admin'@'localhost';
FLUSH PRIVILEGES;
EXIT;
```

## 4. Application Deployment

Clone the repository and set up the virtual environment:
```bash
cd /var/www
sudo git clone <your-repo-url> safar
sudo chown -R $USER:$USER safar
cd safar

python3.11 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn  # Recommended for production
```

## 5. Configuration (.env)

Create a production environment file:
```bash
cp .env.example .env  # Or create a new one
nano .env
```

**Required Changes for Production:**
- `APP_NAME="Safar SFA"`
- `SECRET_KEY`: Generate a random string using `openssl rand -hex 32`.
- `DB_HOST=localhost`
- `DB_PORT=3306` (Standard MySQL port)
- `DB_USER=safar_admin`
- `DB_PASSWORD`: Your strong password from Step 3.
- `JWT_ALGORITHM=HS256`

## 6. Database Initialization

Run the database creation script or migrations:
```bash
python create_db.py
# Or if using Alembic
alembic upgrade head
```

## 7. Systemd Service Configuration

Create a service file to manage the FastAPI process:
```bash
sudo nano /etc/systemd/system/safar.service
```

Paste the following configuration:
```ini
[Unit]
Description=Gunicorn instance to serve Safar SFA
After=network.target

[Service]
User=www-data
Group=www-data
WorkingDirectory=/var/www/safar
Environment="PATH=/var/www/safar/venv/bin"
ExecStart=/var/www/safar/venv/bin/gunicorn \
    -w 4 \
    -k uvicorn.workers.UvicornWorker \
    -b 127.0.0.1:8000 \
    app.main:app

[Install]
WantedBy=multi-user.target
```

Enable and start the service:
```bash
sudo chown -R www-data:www-data /var/www/safar
sudo systemctl start safar
sudo systemctl enable safar
```

## 8. Nginx Reverse Proxy & SSL

Configure Nginx as a reverse proxy:
```bash
sudo nano /etc/nginx/sites-available/safar
```

Paste the following:
```nginx
server {
    listen 80;
    server_name yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

Enable the site and restart Nginx:
```bash
sudo ln -s /etc/nginx/sites-available/safar /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

**Install SSL (Let's Encrypt):**
```bash
sudo apt install python3-certbot-nginx
sudo certbot --nginx -d yourdomain.com
```

## 9. Maintenance Commands

- **Check Logs:** `journalctl -u safar -f`
- **Restart App:** `sudo systemctl restart safar`
- **Update App:**
  ```bash
  cd /var/www/safar
  git pull
  source venv/bin/activate
  pip install -r requirements.txt
  alembic upgrade head
  sudo systemctl restart safar
  ```
