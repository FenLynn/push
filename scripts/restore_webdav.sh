#!/bin/bash
# 📦 Systematic WebDAV Restore Script (Test/Prod Aware) - pg_dump Edition

# 1. Load Environment Configuration
if [ -f ../.env ]; then
    export $(grep -v '^#' ../.env | xargs)
else
    echo "❌ Error: .env file not found in parent directory."
    exit 1
fi

ENC_PASS=${BACKUP_PASSWORD:-}

# 2. Select Source Environment
echo "=============================================="
echo "📥 Restore from which environment?"
echo "=============================================="
echo "1. Test (Local)"
echo "2. Prod (VPS)"
read -p "Enter choice [1/2]: " ENV_CHOICE

if [ "$ENV_CHOICE" == "1" ]; then
    SRC_ENV="test"
elif [ "$ENV_CHOICE" == "2" ]; then
    SRC_ENV="prod"
else
    echo "❌ Invalid choice."
    exit 1
fi

REMOTE_DIR="/push-backup/$SRC_ENV/"
echo "🔍 Listing backups in: $REMOTE_DIR"

echo "⚠️  Note: listing files via curl is raw XML."
curl -s -u "$WEBDAV_USER:$WEBDAV_PASS" -X PROPFIND "$WEBDAV_URL$REMOTE_DIR" --header "Depth: 1" | grep -o "push_backup_${SRC_ENV}_[0-9_]*.tar.gz.enc" | sort | uniq | tail -n 5

echo ""
read -p "📝 Enter backup filename to restore (e.g., push_backup_${SRC_ENV}_20260211_143000.tar.gz.enc): " BACKUP_NAME
# strip spaces
BACKUP_NAME=$(echo $BACKUP_NAME | xargs)

if [ -z "$BACKUP_NAME" ]; then
    echo "❌ Filename cannot be empty."
    exit 1
fi

# 4. Download
cd /nfs/python/push
mkdir -p backups
LOCAL_FILE="backups/$BACKUP_NAME"

echo "☁️  Downloading..."
curl -u "$WEBDAV_USER:$WEBDAV_PASS" -o "$LOCAL_FILE" "$WEBDAV_URL$REMOTE_DIR$BACKUP_NAME"

if [ ! -f "$LOCAL_FILE" ]; then
    echo "❌ Download failed."
    exit 1
fi

# 5. Decrypt
if [[ "$LOCAL_FILE" == *.enc ]]; then
    if [ -z "$ENC_PASS" ]; then
        echo "❌ Error: Encrypted file but BACKUP_PASSWORD not set in .env"
        exit 1
    fi
    
    echo "🔓 Decrypting..."
    DECRYPTED_FILE=${LOCAL_FILE%.enc}
    openssl enc -d -aes-256-cbc -salt -pbkdf2 -iter 100000 \
        -in "$LOCAL_FILE" -out "$DECRYPTED_FILE" -k "$ENC_PASS"
    
    if [ $? -ne 0 ]; then
        echo "❌ Decryption failed! Password mismatch?"
        exit 1
    fi
    TARGET_FILE=$DECRYPTED_FILE
else
    TARGET_FILE=$LOCAL_FILE
fi

# 6. Safety Check
echo "⚠️  WARNING: This will DESTRUCTIVELY restore the database!"
read -p "Are you sure? (yes/no): " CONFIRM
if [ "$CONFIRM" != "yes" ]; then
    echo "❌ Cancelled."
    exit 0
fi

# 7. Restore
echo "📦 Extracting..."
tar -xzf $TARGET_FILE

echo "💾 Restoring Database... (Skipped - TTRSS Removed)"

# Restart all to ensure clean state
echo "🔄 Restarting all services..."
sudo docker compose up -d

echo "✅ Restore Complete!"
