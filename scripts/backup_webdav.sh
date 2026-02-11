#!/bin/bash
# 📦 Systematic WebDAV Backup Script (Test/Prod Aware) - pg_dump Edition

# 1. Load Environment Configuration
if [ -f ../.env ]; then
    export $(grep -v '^#' ../.env | xargs)
else
    echo "❌ Error: .env file not found in parent directory."
    exit 1
fi

# 2. Configuration Validation
if [ -z "$WEBDAV_URL" ] || [ -z "$WEBDAV_PASS" ]; then
    echo "❌ Error: WebDAV credentials missing in .env"
    exit 1
fi

ENV_TYPE=${BACKUP_ENV:-test}     # Default to 'test' if not set
ENC_PASS=${BACKUP_PASSWORD:-}    # Encryption password

echo "=============================================="
echo "🚀 Starting Backup for Environment: [$ENV_TYPE]"
echo "=============================================="

# 3. Prepare Directories
cd /nfs/python/push
mkdir -p backups
BACKUP_DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="push_backup_${ENV_TYPE}_${BACKUP_DATE}.tar.gz"
BACKUP_PATH="backups/$BACKUP_NAME"
DB_DUMP="backups/ttrss_db.sql"

# 4. Dump Database (Crucial Step for Named Volumes)
echo "💾 Dumping TTRSS Database..."
if sudo docker ps | grep -q push-postgres; then
    sudo docker exec push-postgres pg_dump -U ttrss ttrss > $DB_DUMP
    if [ $? -ne 0 ]; then
        echo "❌ Database dump failed!"
        exit 1
    fi
else
    echo "⚠️  Postgres container not running. Skipping DB dump (or failing?)"
    # If not running, maybe we can't backup DB unless we start it.
    # Assuming running for now.
    echo "❌ Error: push-postgres container is not running. Start stack first."
    exit 1
fi

# 5. Create Tarball (DB Dump + Config + Data)
echo "📦 Packing data..."
# Exclude existing backups and system folders
# Note: we include the SQL dump which is in backups/ folder temporarily? No, it's better to put it in root or handle path.
# Let's use specific file list.
tar --exclude='backups/*.tar.gz*' --exclude='__pycache__' \
    -czf $BACKUP_PATH \
    $DB_DUMP \
    .env \
    .private \
    config \
    data/push.db \
    data/task_scheduler.db

# Clean up raw dump
rm $DB_DUMP

# 6. Encrypt (Optional but Recommended)
FINAL_FILE=$BACKUP_PATH
if [ -n "$ENC_PASS" ]; then
    echo "🔒 Encrypting backup..."
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
        -in $BACKUP_PATH -out "${BACKUP_PATH}.enc" -k "$ENC_PASS"
    
    # Remove unencrypted file
    rm $BACKUP_PATH
    FINAL_FILE="${BACKUP_PATH}.enc"
    BACKUP_NAME="${BACKUP_NAME}.enc"
else
    echo "⚠️  Warning: encryption disabled (BACKUP_PASSWORD not set)"
fi

# 7. Upload to WebDAV (Environment Specific Folder)
# Ensure remote directory exists
REMOTE_DIR="/push-backup/$ENV_TYPE/"
echo "☁️  Creating remote directory: $REMOTE_DIR"
curl -s -u "$WEBDAV_USER:$WEBDAV_PASS" -X MKCOL "$WEBDAV_URL/push-backup/" > /dev/null
curl -s -u "$WEBDAV_USER:$WEBDAV_PASS" -X MKCOL "$WEBDAV_URL$REMOTE_DIR" > /dev/null

echo "☁️  Uploading to WebDAV: $REMOTE_DIR"
HTTP_CODE=$(curl -u "$WEBDAV_USER:$WEBDAV_PASS" -T "$FINAL_FILE" \
    -w "%{http_code}" -s -o /dev/null \
    "$WEBDAV_URL$REMOTE_DIR$BACKUP_NAME")

if [ "$HTTP_CODE" -ge 200 ] && [ "$HTTP_CODE" -lt 300 ]; then
    echo "✅ Upload Successful!"
    ls -lh $FINAL_FILE
else
    echo "❌ Upload Failed (HTTP $HTTP_CODE)"
    exit 1
fi

echo "🏁 Done."
