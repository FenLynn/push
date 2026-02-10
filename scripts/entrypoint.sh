#!/bin/bash
set -e

echo "🚀 Starting Push Service..."

# Ensure environment variables are loaded for cron
printenv | grep -v "no_proxy" >> /etc/environment

# Start Cron in background
echo "🕒 Starting Cron..."
service cron start

# Run Init Script (Background)
echo "🔄 Running Auto-Init..."
python /app/scripts/init_ttrss.py &

# Ensure log directory exists
mkdir -p /app/logs
touch /app/logs/app.log

# Run Main Application or keep alive
# We tail the logs so docker logs shows output
echo "✅ Service is running. Monitoring logs..."
tail -f /app/logs/*.log
