# Docker 部署架构详解 (Docker Architecture Explained)

本文档详细解释了本项目 (Push Project) 的容器化部署方案。该方案旨在实现**一键部署、环境隔离、自动调度与数据安全**。

## 1. 核心架构：为什么需要 5 个容器？

我们使用了 Docker Compose 来编排 5 个协同工作的容器。你可以把它们想象成 5 个独立的“虚拟服务器”，通过内部网络连接。

### 🧩 容器清单

| 容器名称 | 角色 | 作用 | 
| :--- | :--- | :--- |
| **push-service** | 🧠 **大脑 (核心业务)** | 运行 Python 脚本 (早报/研报/行情)。**核心特点：内置了 Cron 定时任务**，负责按时触发 `main.py`。 |
| **ttrss** | 📖 **阅读器 (后端)** | Tiny Tiny RSS 的后端程序，负责抓取和管理 RSS 订阅源（如 arxiv, 财新等）。 |
| **db** | 💾 **记忆 (数据库)** | PostgreSQL 数据库。专门存储 TTRSS 的所有订阅数据、文章内容和用户设置。 |
| **ttrss-web** | 🌐 **门面 (前端)** | Nginx 服务器。提供 TTRSS 的网页访问接口 (端口 18100)，让你能登录管理订阅。 |
| **mercury** | 🔍 **解析器 (工具)** | 全文解析服务。TTRSS 使用它来提取网页的正文内容（去除广告和侧边栏）。 |

---

## 2. 自动化调度：告别宿主机 Crontab

在传统的部署中，你需要在 VPS 的操作系统里设置 `crontab -e`。这很难管理，迁移服务器时也容易忘记。

**我们的方案：容器内调度 (Internal Cron)**

- 我们在 `push-service` 容器内部安装了 `cron` 服务。
- 定时任务列表定义在 `config/crontab.txt` 文件中。
- **优势**：
    1. **环境一致性**: 无论你在 Ubuntu, CentOS 还是群晖上运行，定时任务都保证能跑通。
    2. **一键迁移**: 只要拷贝整个项目文件夹，定时任务就自动带走了，无需去新服务器重新配置。

---

## 3. 数据安全：不怕删容器

Docker 的容器是“易失”的（删了容器数据就没了），所以我们使用了 **挂载卷 (Volumes)** 将数据保存在你的硬盘上。

### 📂 关键数据存储位置

| 数据类型 | 本地路径 (VPS) | 容器内路径 | 说明 |
| :--- | :--- | :--- | :--- |
| **TTRSS 数据库** | `docker volume (db_data)` | `/var/lib/postgresql/data` | 最重要！存储了你的 RSS 订阅列表。 |
| **Push 历史库** | `./push.db` | `/app/push.db` | 存储了 Push 发送过的历史记录 (去重用)。 |
| **生成的文件** | `./output/` | `/app/output/` | 每天生成的 HTML 和 Markdown 报告。 |
| **日志文件** | `./logs/` | `/app/logs/` | 定时任务的运行日志，方便排错。 |
| **配置文件** | `.env` | (环境变量) | 存储了 Token 和 密码。 |

---

## 4. 备份与恢复：一键“后悔药”

为了防止 VPS 故障或误操作，我们提供了傻瓜式的备份脚本。

### 🛡️ 备份脚本 (`scripts/backup.sh`)
运行 `./scripts/backup.sh`，它会自动做以下事情：
1.用于 `pg_dump` 命令将 Postgres 数据库导出为 SQL 文件。
2.打包 `push.db` 和 `output` 目录。
3.打包 `.env` 和配置文件。
4.生成一个 `push_backup_日期.tar.gz` 压缩包。

**建议**: 你可以将这个压缩包下载到本地，或者上传到网盘。

### 🏥 恢复脚本 (`scripts/restore.sh`)
在新服务器上，只需运行 `./scripts/restore.sh <备份包>`，系统就会瞬间恢复到备份时的状态。

---

## 5. 部署流程 (Quick Start)

1.  **上传代码**: 将 `push` 文件夹上传到 VPS。
2.  **配置环境**: 
    ```bash
    cp .env.example .env
    nano .env  # 填入你的 Token 和 密码
    ```
3.  **启动服务**:
    ```bash
    ./start.sh
    # 或者 docker-compose up -d
    ```
4.  **初始化 TTRSS** (仅首次):
    - 访问 `http://<VPS_IP>:18100`。
    - 登录 (默认账号 admin / password)。
    - **导入 OPML**: 在设置中导入你之前的 RSS 订阅文件。

🎉 **完成！系统现在会自动运行，并每天推送日报。**
