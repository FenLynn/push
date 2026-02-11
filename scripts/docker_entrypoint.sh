#!/bin/bash
set -e

# === Docker Entrypoint for Push Service ===

echo "🚀 Starting Push Service Entrypoint..."

# 1. Environment Check
echo "🔍 Checking environment..."
if [ -z "$PUSHPLUS_TOKEN" ]; then
    echo "⚠️  WARNING: PUSHPLUS_TOKEN is not set! Push notifications may fail."
fi

# 2. Font Check (should be baked in image)
if fc-list :lang=zh | grep -q "Noto Sans CJK"; then
    echo "✅ Chinese fonts found (Noto Sans CJK)."
else
    echo "⚠️  Chinese fonts NOT found. Charts may have issues."
fi

# 3. Private Config Init (Restore default if missing)
if [ ! -f "/app/.private/stock.json" ]; then
    echo "🛠️  Initializing default stock.json..."
    echo '{"stock": [{"code": "sh600519", "name": "贵州茅台"}, {"code": "sz000858", "name": "五粮液"}]}' > /app/.private/stock.json
fi
if [ ! -f "/app/.private/etf.json" ]; then
    echo "🛠️  Initializing default etf.json..."
    echo '{"etf": [{"code": "sh510300", "name": "沪深300ETF"}]}' > /app/.private/etf.json
fi
if [ ! -f "/app/.private/fund.json" ]; then
    echo "🛠️  Initializing default fund.json..."
    echo '{"fund": [{"code": "000001", "name": "华夏成长"}]}' > /app/.private/fund.json
fi

# 4. Start Cron Daemon (Disabled: managed by Ofelia)
# echo "⏰ Starting Cron daemon..."
# service cron start

# 5. Keep Container Running (Tail logs)
echo "✅ Service is ready. Tailing logs..."
# Create log file if not exists
touch /app/logs/push.log
tail -f /app/logs/push.log
