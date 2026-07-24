#!/bin/bash
# 1. Run migrations to ensure the database schema is up-to-date
echo "Running database migrations..."
python3 db_migrate.py

# 2. Find and kill the process on port 8001 if running
PID=$(lsof -ti:8090)
if [ ! -z "$PID" ]; then
    echo "Killing process $PID on port 8090..."
    kill -9 $PID
else
    echo "No process running on port 8090."
fi

# 3. Start Sastrybalm
echo "Starting Sastrybalm..."
nohup python3 run.py > sastrybalm.log 2>&1 &
echo "Sastrybalm started on port 8090. Logs are in sastrybalm.log"
