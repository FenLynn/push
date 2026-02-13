# VPS 部署指南 (Docker + Ofelia)

既然 GitHub Actions 构建已通过，您的镜像已经成功推送到 `ghcr.io/fenlynn/push:main`。以下是将其部署到 VPS 的步骤。

## 1. 克隆代码仓库

由于是私有仓库，您可以使用 **GitHub Personal Access Token (PAT)** 进行克隆。这样最简单，无需配置 SSH Key：

```bash
# 在 VPS 上执行 (将 YOUR_PAT 替换为您的 Token)
git clone https://YOUR_PAT@github.com/FenLynn/push.git
cd push
```

### 🌐 网络加速 (针对国内 VPS)

如果您在克隆时卡住或提示 `Connection timed out`，按照以下顺序尝试：

#### 方案 A：修改 /etc/hosts 解决 DNS 污染 (最稳、最推荐)
这是目前国内 VPS 直连 GitHub 最有效的办法。
1. 编辑文件：`sudo vi /etc/hosts`
2. 在末尾添加以下映射（确保 IP 为 GitHub 官方 CDN 地址）：
   ```text
   140.82.113.3      github.com
   185.199.108.153   github.io
   199.232.69.194    github.global.ssl.fastly.net
   ```
3. 保存退出，然后再次尝试原始克隆命令。

#### 方案 B：使用 --depth 1 (减小传输量)
即使修改了 hosts，配合“浅克隆”可以极速完成，不拉取冗余历史记录：
```bash
git clone --depth 1 https://YOUR_PAT@github.com/FenLynn/push.git
```

#### 方案 C：使用加速代理 (备选)
如果直连依然感人，请尝试目前较稳的镜像：
```bash
# 镜像 1
git clone --depth 1 https://YOUR_PAT@kkgithub.com/FenLynn/push.git
# 镜像 2
git clone --depth 1 https://YOUR_PAT@gitmirror.com/FenLynn/push.git
```


## 2. 准备 VPS 环境

如果您的 VPS 还没有安装 Docker，可以使用项目内置的脚本（针对 CentOS 9）：

```bash
# 在 VPS 上执行
bash scripts/install_docker.sh
```

对于其他系统（如 Ubuntu），请参考 Docker 官方文档安装 Docker 和 Docker Compose V2。

## 2. GitHub 镜像仓库登录

在 VPS 上登录 GitHub Container Registry，以便能够下载私有镜像：

```bash
# 请先在 GitHub 个人设置中生成一个具有 read:packages 权限的 Token (PAT)
echo "YOUR_GITHUB_PAT" | docker login ghcr.io -u YOUR_GITHUB_USERNAME --password-stdin
```

## 3. 部署服务

1. **上传配置文件**: 将本地的 `docker-compose.yml` 和 `.env` 上传到 VPS 的部署目录（例如 `/opt/push`）。
2. **初始化目录**: 确保 VPS 上存在 `logs`, `output`, `data`, `.private` 等目录，或者由 Docker 自动创建。
3. **启动容器**:

```bash
# 在部署目录下执行
docker-compose pull
docker-compose up -d
```

## 4. 验证运行状态

```bash
# 查看容器状态
docker-compose ps

# 查看运行日志
docker-compose logs -f push-service
```

## 常见问题 (FAQ)

- **代码挂载**: `docker-compose.yml` 中默认开启了代码挂载 (`./core:/app/core` 等)。如果您在 VPS 上不打算放置源代码，请注释掉 `volumes` 下对应的代码行，直接使用镜像内自带的源码。
- **定时任务**: 定时任务由 `push-ofelia` 容器管理，它会根据 `push-service` 的 `labels` 自动触发任务。您可以通过 `docker logs push-ofelia` 查看调度情况。
- **环境变量**: 确保 VPS 上的 `.env` 文件包含了所有必要的 Key (如 `PUSHPLUS_TOKEN`, `CLOUDFLARE_D1_*`)。
