# Push - 多功能信息推送系统

这是一个基于 Python 的多功能信息推送系统，遵循 IFTTT (If This Then That) 模式，旨在将分散的信息（天气、股市、论文、赛程、影视等）通过统一的接口推送到微信等通道。

## 🌟 核心特性

- **IFTTT 架构**: 数据源 (Source) 与推送通道 (Channel) 完全解耦
- **模块化设计**: 轻松添加新的信息源或推送方式
- **统一入口**: 通过 `main.py` 即可管理和运行所有任务
- **定时调度**: 内置 Cron 自动化执行
- **任务监控**: 每日摘要报告 (23:00) ，显示成功/失败模块
- **数据备份**: 支持 WebDAV 自动备份

## 🚀 一键部署 (Docker)

### 1. 配置环境变量

```bash
# 复制配置模板
cp .env.example .env
cp config.ini.example config.ini

# 编辑 .env，填写必填项：
# - PUSHPLUS_TOKEN: 你的 PushPlus 令牌 (必填)
# - DB_PASS: 数据库密码
# - TTRSS_PASSWORD: TTRSS 登录密码
# - SMMS_TOKEN: SMMS 图片上传令牌 (推荐)
# - PUSH_ENV: 环境标识 (可选, 如 local/server)
# - TTRSS_URL: TTRSS 地址 (可选, 覆盖默认配置)
```

### 2. 启动服务

```bash
docker-compose up -d
```

### 3. 验证运行

```bash
# 查看服务状态
docker-compose ps

# 查看日志
docker-compose logs -f push-service
```

**就这么简单！服务会自动：**
- 初始化 TTRSS 并导入 OPML 订阅
- 按照 `config/crontab.txt` 的时间表自动执行推送
- 每日 23:00 发送执行摘要报告

## 📁 目录结构

```
push/
├── main.py              # 统一命令行入口
├── docker-compose.yml   # Docker 编排
├── Dockerfile           # 容器构建
├── requirements.txt     # Python 依赖
│
├── core/                # 核心引擎
│   ├── engine.py       # 推送引擎
│   ├── env.py          # 环境配置
│   ├── task_scheduler.py # 任务调度器
│   ├── trading_calendar.py # 交易日判断
│   └── cache_db.py     # 统一缓存数据库
│
├── sources/             # 数据源
│   ├── morning/        # 早报
│   ├── finance/        # 财经日报
│   ├── paper/          # 论文 (TTRSS)
│   └── ...
│
├── channels/            # 推送通道
│   └── pushplus.py     # PushPlus 微信推送
│
├── scripts/             # 脚本工具
│   ├── entrypoint.sh   # Docker 入口
│   ├── upgrade.sh      # 零停机升级
│   ├── backup_webdav.py # WebDAV 备份
│   ├── restore_webdav.py # 数据恢复
│   └── daily_summary.py # 每日摘要
│
├── config/              # 配置文件
│   ├── crontab.txt     # 定时任务
│   └── nginx.conf      # TTRSS Nginx
│
└── templates/           # HTML 模板
```

## 📋 可用模块

| 模块 | 说明 | 运行时机 |
|------|------|----------|
| `morning` | 早报 (天气/金融/英语) | 每天 08:00 |
| `paper` | 论文 (TTRSS) | 每天 08:00 |
| `finance` | 财经日报 | A股交易日 18:00 |
| `stock` | 股票行情 | A股交易日 18:00 |
| `etf` | ETF 监控 | A股交易日 18:00 |
| `fund` | 基金估值 | A股交易日 18:00 |
| `night` | 美股夜盘 | 美股交易日次日 07:00 |
| `game` | 游戏赛程 | 每天 12:00 |
| `estate` | 成都房产 | 周一工作日 09:00 |

## 🔧 常用命令

```bash
# 手动运行模块
docker exec push-service python main.py run finance stock

# 运行模块组
docker exec push-service python main.py run @stock  # finance, stock, etf, fund
docker exec push-service python main.py run @all    # 所有模块

# 查看可用模块
docker exec push-service python main.py list

# 零停机升级
./scripts/upgrade.sh

# 手动备份到 WebDAV
docker exec push-service python scripts/backup_webdav.py
```

## 🔒 安全说明

- TTRSS 仅监听 `127.0.0.1:18100`，公网无法直接访问
- 访问 TTRSS 需通过 SSH 隧道：`ssh -L 18100:localhost:18100 user@your-vps`
- 所有敏感信息均在 `.env` 中配置，不会提交到 Git

## 📚 更多文档

- [Docker 部署手册](docs/DOCKER_MANUAL.md)
- [架构设计文档](ARCHITECTURE.md)
- [环境配置说明](ENV_CONFIG.md)

## 📄 开源协议

MIT License
