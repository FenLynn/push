#!/bin/bash
set -e

# Configuration
BACKUP_DIR="./backups"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
FILENAME="push_backup_${TIMESTAMP}.tar.gz"
TEMP_DIR="./temp_backup_${TIMESTAMP}"

mkdir -p "$BACKUP_DIR"
mkdir -p "$TEMP_DIR"

echo "📦 Starting Backup: ${FILENAME}..."

# 1. Backup Postgres (TTRSS)
echo "   - Dumping Postgres Database..."
docker exec -t postgres-db pg_dumpall -c -U ttrss > "$TEMP_DIR/ttrss_db.sql"

# 2. Backup SQLite (Push History)
echo "   - Copying Push DB..."
cp ./push.db "$TEMP_DIR/push.db"

# 3. Backup Output (Generated Reports)
echo "   - Copying Output artifacts..."
cp -r ./output "$TEMP_DIR/output"

# 4. Backup Configs
echo "   - Copying Configs..."
cp .env "$TEMP_DIR/.env"
cp docker-compose.yml "$TEMP_DIR/docker-compose.yml"
cp -r config "$TEMP_DIR/config"

# 5. Compress
echo "   - Compressing..."
tar -czf "$BACKUP_DIR/$FILENAME" -C "$TEMP_DIR" .

# 6. Cleanup
rm -rf "$TEMP_DIR"

echo "✅ Backup Complete: ${BACKUP_DIR}/${FILENAME}"
