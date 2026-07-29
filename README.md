# Amigoo SFA

## Database Management

If you need to manually drop the database, recreate it, and run database migrations, you can use the following Docker commands from your terminal.

### 1. Drop the Database
Run this command to drop the existing database (this will permanently delete all data):
```bash
docker exec safar-db mysql -uroot -prootpassword -e "DROP DATABASE IF EXISTS safar_db;"
```

### 2. Create the Database
Run this command to create a fresh, empty database:
```bash
docker exec safar-db mysql -uroot -prootpassword -e "CREATE DATABASE safar_db;"
```

### 3. Run Migrations
Run this command inside the app container to create the necessary tables and seed initial data:
```bash
docker compose exec app alembic upgrade head
```
