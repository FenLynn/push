#!/bin/bash
# TTRSS Initialization Script
# Automatically create admin user and import subscriptions

set -e

echo "=== TTRSS Auto-Initialization ==="

# Wait for TTRSS to be fully ready
echo "⏳ Waiting for TTRSS to start..."
sleep 10

# Check if TTRSS is accessible
MAX_RETRIES=30
RETRY_COUNT=0
while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -s http://ttrss-web/ > /dev/null 2>&1; then
        echo "✅ TTRSS is responding"
        break
    fi
    RETRY_COUNT=$((RETRY_COUNT+1))
    echo "   Attempt $RETRY_COUNT/$MAX_RETRIES..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    echo "❌ TTRSS failed to start after $MAX_RETRIES attempts"
    exit 1
fi

# Create admin user if not exists
ADMIN_USER=${TTRSS_USERNAME:-admin}
ADMIN_PASS=${TTRSS_PASSWORD:-admin_secure_password}

echo "👤 Creating admin user..."
docker exec push-ttrss-app /bin/sh -c "
    cd /var/www/html && \
    php ./update.php --user-add \"$ADMIN_USER\" \"$ADMIN_PASS\" 0 || \
    echo 'User already exists or creation failed (this is OK if user exists)'
"

# Set admin privileges
docker exec push-ttrss-app /bin/sh -c "
    cd /var/www/html && \
    php ./update.php --user-set-password \"$ADMIN_USER\" \"$ADMIN_PASS\" || true
"

echo "✅ Admin user configured: $ADMIN_USER"

# Import OPML subscriptions if exists
if [ -f "./config/subscriptions.opml" ]; then
    echo "📥 Importing subscriptions from OPML..."
    docker cp ./config/subscriptions.opml push-ttrss-app:/tmp/subscriptions.opml
    docker exec push-ttrss-app /bin/sh -c "
        cd /var/www/html && \
        php ./update.php --opml-import /tmp/subscriptions.opml \"$ADMIN_USER\"
    " || echo "⚠️  OPML import may need manual intervention via web UI"
else
    echo "⚠️  No subscriptions.opml found in ./config/"
fi

echo ""
echo "🎉 TTRSS Initialization Complete!"
echo ""
echo "📝 Login Information:"
echo "   URL: http://localhost:18100"
echo "   Username: $ADMIN_USER"
echo "   Password: $ADMIN_PASS"
echo ""
echo "⚠️  Remember to change the password after first login!"
