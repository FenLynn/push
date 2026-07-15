# Push

基于 GitHub Actions 和 Cloudflare 的定时信息采集、归档与消息推送项目。

## 运行架构

- GitHub Actions 运行各业务模块和 RSS 抓取任务。
- Cloudflare 负责定时触发，并使用 D1、R2 保存结构化数据和生成结果。
- PushPlus 等外部服务负责消息投递。
- 运行密钥由 GitHub Secrets 注入，不保存在仓库中。

项目不再提供或维护 Docker、Docker Compose、Ofelia 和 VPS 容器部署方式。

## 目录

- `core/`：配置、调度、日志和消息生成等核心逻辑。
- `sources/`：各业务数据源。
- `channels/`：消息投递渠道。
- `scripts/`：GitHub Actions 和维护脚本。
- `.github/workflows/`：各模块的 GitHub Actions 工作流。
- `cf-cron/`：Cloudflare 定时触发服务。

## 本地运行

创建不会被 Git 跟踪的 `.env`，配置所需变量后执行：

```bash
python main.py list
python main.py run <module> --topic <topic>
```

是否绕过模块自身的日期或时段检查，可使用：

```bash
python main.py run <module> --topic <topic> --force
```

## GitHub Actions

各模块工作流直接安装 Python 依赖并执行 `main.py` 或对应脚本，不依赖容器环境。环境配置由仓库 Secret `PUSH_ENV_FILE` 在 Runner 上临时加载。

运行产物、日志、本地数据和 `.env` 均由 `.gitignore` 排除，不应提交到仓库。
