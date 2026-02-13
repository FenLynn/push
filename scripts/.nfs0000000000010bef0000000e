#!/bin/sh
# TTRSS自动初始化脚本
# 在容器启动后自动设置密码和导入OPML

set -e

echo "=== TTRSS Auto-Init Starting ==="

# 等待TTRSS完全启动
sleep 15

# 设置管理员密码
echo "📝 Setting admin password..."
cd /var/www && php update.php --user-set-password admin "${TTRSS_ADMIN_PASSWORD:-push_admin_2026}" 2>/dev/null || echo "⚠️  Password set failed (may already be set)"

# 导入OPML配置
if [ -f "/opml/tt-rss_admin_2026-02-08.opml" ]; then
    echo "📥 Importing OPML subscriptions..."
    cd /var/www && php update.php --opml-import /opml/tt-rss_admin_2026-02-08.opml admin 2>/dev/null || echo "⚠️  OPML import may have failed"
    echo "✅ OPML import attempted"
else
    echo "⚠️  OPML file not found at /opml/tt-rss_admin_2026-02-08.opml"
fi

echo "=== TTRSS Auto-Init Complete ==="
