#!/bin/bash
# =============================================================================
# Docker镜像构建与推送脚本
# Docker Image Build and Push Script
# =============================================================================
set -e

# 从.env读取配置(如果存在)
if [ -f .env ]; then
    export $(grep -v '^#' .env | xargs)
fi

# 镜像名称配置
REGISTRY=${DOCKER_REGISTRY:-"ghcr.io/yourusername"}
IMAGE_NAME="push-service"
VERSION=${1:-"latest"}

FULL_IMAGE="${REGISTRY}/${IMAGE_NAME}:${VERSION}"

echo "🐳 构建Docker镜像..."
echo "镜像名称: ${FULL_IMAGE}"

# 构建镜像
docker build -t "${FULL_IMAGE}" .

# 同时打latest标签
if [ "$VERSION" != "latest" ]; then
    docker tag "${FULL_IMAGE}" "${REGISTRY}/${IMAGE_NAME}:latest"
fi

echo "✅ 构建完成"

# 询问是否推送
read -p "是否推送到镜像仓库? (y/n): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    echo "☁️  推送镜像到 ${REGISTRY}..."
    docker push "${FULL_IMAGE}"
    
    if [ "$VERSION" != "latest" ]; then
        docker push "${REGISTRY}/${IMAGE_NAME}:latest"
    fi
    
    echo "✅ 推送完成!"
else
    echo "⏭️  跳过推送"
fi

echo "
📦 镜像信息:
   名称: ${FULL_IMAGE}
   大小: $(docker images ${FULL_IMAGE} --format "{{.Size}}")
   
🚀 使用方式:
   docker pull ${FULL_IMAGE}
   docker run -d --env-file .env ${FULL_IMAGE}
"
