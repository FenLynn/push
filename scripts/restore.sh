#!/bin/bash
set -e

if [ -z "$1" ]; then
    echo "Usage: ./restore.sh <backup_file.tar.gz>"
    exit 1
fi

BACKUP_FILE="$1"
TEMP_DIR="./temp_restore"

echo "⚠️  Restoring from: ${BACKUP_FILE}"
echo "⚠️  This will OVERWRITE current data. Press Ctrl+C to cancel in 5 seconds..."
sleep 5

mkdir -p "$TEMP_DIR"
tar -xzf "$BACKUP_FILE" -C "$TEMP_DIR"

# 1. Restore Configs
echo "   - Restoring Configs..."
cp "$TEMP_DIR/.env" .
cp "$TEMP_DIR/docker-compose.yml" .
cp -r "$TEMP_DIR/config" .

# 2. Restore SQLite
echo "   - Restoring Push DB..."
cp "$TEMP_DIR/push.db" .

# 3. Restore Output
echo "   - Restoring Output..."
cp -r "$TEMP_DIR/output" .

# 4. Restore Postgres (Skipped - TTRSS Removed)

# Cleanup
rm -rf "$TEMP_DIR"

echo "✅ Restore Complete. Please restart containers: docker-compose up -d"
