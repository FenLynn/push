#!/bin/bash
# Docker Installation Script for CentOS 9 (China Mirror)
# 使用阿里云镜像安装Docker

set -e

echo "=== Docker 安装脚本 (CentOS 9 + 阿里云镜像) ==="

# 1. 卸载旧版本(如果有)
echo "步骤 1: 卸载旧版本..."
sudo yum remove -y docker docker-client docker-client-latest docker-common \
    docker-latest docker-latest-logrotate docker-logrotate docker-engine \
    podman runc 2>/dev/null || true

# 2. 安装依赖
echo "步骤 2: 安装依赖包..."
sudo yum install -y yum-utils device-mapper-persistent-data lvm2

# 3. 添加阿里云Docker仓库
echo "步骤 3: 配置阿里云Docker仓库..."
sudo yum-config-manager --add-repo \
    https://mirrors.aliyun.com/docker-ce/linux/centos/docker-ce.repo

# 4. 安装Docker CE
echo "步骤 4: 安装Docker CE..."
sudo yum install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin

# 5. 启动Docker
echo "步骤 5: 启动Docker服务..."
sudo systemctl start docker
sudo systemctl enable docker

# 6. 配置Docker镜像加速(使用多个国内镜像源)
echo "步骤 6: 配置Docker镜像加速..."
sudo mkdir -p /etc/docker
sudo tee /etc/docker/daemon.json > /dev/null <<EOF
{
  "registry-mirrors": [
    "https://docker.m.daocloud.io",
    "https://dockerproxy.com",
    "https://docker.nju.edu.cn",
    "https://docker.mirrors.sjtug.sjtu.edu.cn"
  ],
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "10m",
    "max-file": "3"
  }
}
EOF

# 7. 重启Docker应用配置
echo "步骤 7: 重启Docker..."
sudo systemctl daemon-reload
sudo systemctl restart docker

# 8. 安装Docker Compose V2 (Plugin模式)
echo "步骤 8: 安装Docker Compose..."
# Docker Compose V2已作为插件包含在docker-buildx-plugin中
# 创建兼容别名
sudo ln -sf /usr/libexec/docker/cli-plugins/docker-compose /usr/local/bin/docker-compose 2>/dev/null || true

# 9. 配置当前用户权限(避免每次sudo)
echo "步骤 9: 配置用户权限..."
sudo usermod -aG docker $USER

# 10. 测试安装
echo "步骤 10: 测试Docker..."
sudo docker --version
sudo docker compose version || sudo docker-compose --version

echo ""
echo "✅ Docker 安装完成!"
echo ""
echo "⚠️  注意: 当前用户已添加到docker组,但需要重新登录才能生效。"
echo "   临时方案: 使用 'sudo docker' 或 'newgrp docker' 激活权限"
echo ""
echo "📝 已配置的镜像源:"
echo "   - DaoCloud: docker.m.daocloud.io"
echo "   - DockerProxy: dockerproxy.com"
echo "   - 南京大学: docker.nju.edu.cn"
echo "   - 上海交大: docker.mirrors.sjtug.sjtu.edu.cn"
echo ""
echo "🧪 测试命令: sudo docker run hello-world"
