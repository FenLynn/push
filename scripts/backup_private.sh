#!/bin/bash
# =============================================================================
# 私有数据与输出备份脚本
# Backup Script for Private Data and Outputs
# =============================================================================
set -e

BACKUP_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="push_backup_${DATE}"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

echo "🔄 开始备份私有数据..."

# 打包私有数据和输出
tar -czf "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz" \
    .private/ \
    output/ \
    --exclude='output/*.tmp' \
    --exclude='*.log'

echo "✅ 打包完成: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"

# 如果设置了加密密钥,则加密
if [ -n "$BACKUP_GPG_PASSPHRASE" ]; then
    echo "🔐 加密备份文件..."
    echo "$BACKUP_GPG_PASSPHRASE" | gpg --batch --yes --passphrase-fd 0 \
        --symmetric --cipher-algo AES256 \
        "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    
    # 删除未加密版本
    rm "${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
    echo "✅ 加密完成: ${BACKUP_DIR}/${BACKUP_NAME}.tar.gz.gpg"
    FINAL_FILE="${BACKUP_NAME}.tar.gz.gpg"
else
    echo "⚠️  未设置BACKUP_GPG_PASSPHRASE,跳过加密"
    FINAL_FILE="${BACKUP_NAME}.tar.gz"
fi

# 上传到网盘 (需配置rclone)
if command -v rclone &> /dev/null; then
    if rclone listremotes | grep -q "webdav"; then
        echo "☁️  上传到WebDAV..."
        rclone copy "${BACKUP_DIR}/${FINAL_FILE}" webdav:/push_backups/
        echo "✅ 上传完成"
    else
        echo "⚠️  未配置rclone webdav远程,跳过上传"
    fi
else
    echo "⚠️  未安装rclone,跳过上传。安装: https://rclone.org/install/"
fi

# 清理旧备份 (保留最近7天)
echo "🧹 清理7天前的备份..."
find "$BACKUP_DIR" -name "push_backup_*.tar.gz*" -mtime +7 -delete

echo "✅ 备份完成!"
