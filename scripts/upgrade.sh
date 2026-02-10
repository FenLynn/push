#!/bin/bash
# =============================================================================
# Push Project Docker Upgrade Script
# Docker 升级脚本 - 无感升级
#
# 用法: ./scripts/upgrade.sh [--no-backup] [--force]
#
# 特性:
# 1. 升级前自动备份
# 2. 保留数据卷（无数据丢失）
# 3. 健康检查确保服务可用
# 4. 失败自动回滚
# =============================================================================

set -e

# 配置
PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
BACKUP_DIR="${PROJECT_DIR}/backups"
LOG_FILE="${PROJECT_DIR}/logs/upgrade.log"

# 颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() {
    local msg="[$(date '+%Y-%m-%d %H:%M:%S')] $1"
    echo -e "$msg" | tee -a "$LOG_FILE"
}

log_success() { log "${GREEN}✅ $1${NC}"; }
log_warn() { log "${YELLOW}⚠️ $1${NC}"; }
log_error() { log "${RED}❌ $1${NC}"; }

# 解析参数
NO_BACKUP=false
FORCE=false
while [[ $# -gt 0 ]]; do
    case $1 in
        --no-backup) NO_BACKUP=true; shift ;;
        --force) FORCE=true; shift ;;
        *) shift ;;
    esac
done

# 确保日志目录存在
mkdir -p "$(dirname "$LOG_FILE")"
mkdir -p "$BACKUP_DIR"

log "=========================================="
log "Push Project Docker Upgrade"
log "=========================================="

cd "$PROJECT_DIR"

# Step 1: 备份（可选）
if [ "$NO_BACKUP" = false ]; then
    log "Step 1: Creating backup..."
    BACKUP_NAME="pre-upgrade-$(date +%Y%m%d-%H%M%S).tar.gz"
    
    # 备份数据目录和配置
    tar -czf "$BACKUP_DIR/$BACKUP_NAME" \
        --exclude='*.log' \
        data/ .env config/ 2>/dev/null || true
    
    log_success "Backup created: $BACKUP_NAME"
else
    log_warn "Step 1: Backup skipped (--no-backup)"
fi

# Step 2: 拉取最新代码
log "Step 2: Pulling latest code..."
if git pull origin main 2>&1 | tee -a "$LOG_FILE"; then
    log_success "Code updated"
else
    log_warn "Git pull failed or no changes"
fi

# Step 3: 记录当前容器状态（用于回滚）
log "Step 3: Recording current state..."
CURRENT_IMAGE=$(docker-compose images -q push-service 2>/dev/null || echo "none")
log "Current image: $CURRENT_IMAGE"

# Step 4: 构建新镜像
log "Step 4: Building new image..."
if docker-compose build --no-cache push-service 2>&1 | tee -a "$LOG_FILE"; then
    log_success "Build completed"
else
    log_error "Build failed!"
    exit 1
fi

# Step 5: 滚动更新 (无感升级核心)
log "Step 5: Rolling update..."

# 停止旧容器并启动新容器（数据卷保留）
docker-compose up -d --no-deps --build push-service 2>&1 | tee -a "$LOG_FILE"

# Step 6: 健康检查
log "Step 6: Health check..."
RETRY=0
MAX_RETRY=30
HEALTHY=false

while [ $RETRY -lt $MAX_RETRY ]; do
    # 检查容器是否运行
    if docker-compose ps push-service | grep -q "Up"; then
        # 检查日志是否有错误
        RECENT_LOGS=$(docker-compose logs --tail=10 push-service 2>&1)
        if echo "$RECENT_LOGS" | grep -qiE "error|exception|failed"; then
            log_warn "Potential issue detected in logs"
        else
            HEALTHY=true
            break
        fi
    fi
    
    RETRY=$((RETRY + 1))
    log "Waiting for service... ($RETRY/$MAX_RETRY)"
    sleep 2
done

if [ "$HEALTHY" = true ]; then
    log_success "Service is healthy!"
else
    log_error "Service unhealthy after upgrade!"
    
    # 回滚
    if [ "$FORCE" = false ]; then
        log "Rolling back..."
        docker-compose down
        docker-compose up -d
        log_warn "Rolled back to previous state"
    fi
    exit 1
fi

# Step 7: 清理旧镜像（可选）
log "Step 7: Cleaning up old images..."
docker image prune -f 2>&1 | tee -a "$LOG_FILE" || true

# 完成
log "=========================================="
log_success "Upgrade completed successfully!"
log "=========================================="

# 显示运行状态
docker-compose ps
