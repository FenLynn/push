# Docker 部署架构详解 (Simplified Architecture)

本文档详细解释了本项目 (Push Project) 简化后的容器化部署方案。该方案旨在实现**轻量级、零数据库维护、云端协同**。

## 1. 核心架构：化繁为简

随着 Paper 模块向云原生架构 (Cloudflare D1) 迁移，我们大幅简化了本地部署。现在，你不再需要维护笨重的 TTRSS 及其关联的数据库。

### 🧩 容器清单

| 容器名称 | 角色 | 作用 | 
| :--- | :--- | :--- |
| **push-service** | 🧠 **大脑 (核心业务)** | 运行 Python 脚本 (早报/周报/研报)。现在直接从 API 或 D1 抓取数据，不再依赖本地数据库。 |
| **push-ofelia** | ⏰ **时钟 (调度器)** | Ofelia 容器。作为一个轻量级的 Docker 原生调度器，它通过 labels 控制 `push-service` 按时运行各种模块。 |

> **注：** 我们已彻底移除 `ttrss` (阅读器)、`db` (Postgres) 和 `mercury` (解析器)，服务器内存占用降低了约 70%。

---

## 2. 自动化调度：Docker 原生

我们采用 **Ofelia** 替代了内部 Cron，这样你可以直接在 `docker-compose.yml` 中可视化管理所有计划任务。

**优势**：
1. **透明化**: 直接运行 `docker logs push-ofelia` 即可看到所有调度记录。
2. **免维护**: 不需要进入容器修改 crontab 文件。
3. **弹性调整**: 修改 `docker-compose.yml` 里的 labels 即可调整推送时间。

---

## 3. 数据持久化：轻装上阵

现在只有必须要保存的数据才会被保留在宿主机。

### 📂 关键数据存储位置

| 数据类型 | 本地路径 (VPS) | 容器内路径 | 说明 |
| :--- | :--- | :--- | :--- |
| **Push 历史库** | `./data/` | `/app/data/` | 存储 SQLite 数据库（如 `push.db`），用于记录已发送的消息以防重复。 |
| **生成的文件** | `./output/` | `/app/output/` | 每天生成的 HTML 和 Markdown 报告。 |
| **日志文件** | `./logs/` | `/app/logs/` | 应用运行日志，方便排错。 |
| **配置文件** | `.env` | (环境变量) | 存储核心 Token 和 密钥。 |

---

## 4. 备份与恢复

虽然去掉了 Postgres，但备份依然重要。

### 🛡️ 备份脚本 (`scripts/backup_r2.py`)
我们现在推荐使用 R2 或 WebDAV 备份脚本。它会：
1. 打包 `./data` (SQLite 数据库)。
2. 打包 `.env` 和 `config/` 目录。
3. 加密并上传到云端 (Cloudflare R2 或 坚果云)。

---

## 5. 快速开始 (Quick Start)

1.  **配置环境**: 
    ```bash
    cp .env.example .env
    nano .env  # 填写各项 Token
    ```
2.  **启动服务**:
    ```bash
    docker-compose up -d
    ```
3.  **手动测试**:
    ```bash
    docker exec -it push-service python main.py run paper
    ```

🎉 **系统现在进入了极简运行模式。所有 RSS 抓取逻辑已托管至 GitHub Actions，本地仅负责报告生成与推送。**
