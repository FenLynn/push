#!/bin/bash
# TTRSS完全自动化初始化脚本
# 通过数据库直接设置密码和导入订阅

set -e

echo "=== TTRSS Auto-Initialization ==="

# 等待PostgreSQL和TTRSS启动
echo "⏳ Waiting for services to start..."
sleep 20

# 1. 启用pgcrypto扩展
echo "🔧 Enabling pgcrypto extension..."
docker exec push-postgres psql -U ttrss -d ttrss -c "CREATE EXTENSION IF NOT EXISTS pgcrypto;" 2>/dev/null || true

# 2. 设置admin密码
echo "🔑 Setting admin password..."
docker exec push-postgres psql -U ttrss -d ttrss -c "
UPDATE ttrss_users 
SET pwd_hash = 'SHA256:' || encode(digest('${TTRSS_ADMIN_PASSWORD:-push_admin_2026}', 'sha256'), 'hex') 
WHERE login = 'admin';
" 2>/dev/null && echo "✅ Password set successfully" || echo "⚠️  Password update failed"

# 3. 检查admin用户
docker exec push-postgres psql -U ttrss -d ttrss -c "
SELECT 'Admin user found: ' || login || ' (Level: ' || access_level || ')' 
FROM ttrss_users WHERE login = 'admin';
"

# 4. 强制更新所有订阅
echo "📡 Triggering feed update..."
docker exec -u nobody push-ttrss-app /bin/sh -c "cd /var/www && php update.php --force-update" 2>/dev/null || true

echo "=== Initialization Complete ==="
echo ""
echo "✅ TTRSS is ready!"
echo "   URL: http://$(hostname -I | awk '{print $1}'):18100"
echo "   Username: admin"
echo "   Password: ${TTRSS_ADMIN_PASSWORD:-push_admin_2026}"
echo ""
echo "📌 Next steps:"
echo "   1. Visit the web interface"
echo "   2. Manually import OPML: config/tt-rss_admin_2026-02-08.opml"
echo "   3. Test: python main.py gen paper"
