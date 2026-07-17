# Finance 的 Cloudflare Cron 设计

## 一句话结构

Cloudflare Worker 负责“几点运行”，GitHub Actions 只负责“收到请求后执行什么”。

```text
Cloudflare Cron（每分钟唤醒）
  -> cf_cron_script.js 按北京时间匹配 ROUTE_CONFIG
  -> GitHub workflow_dispatch API
  -> .github/workflows/finance.yml
  -> python main.py gen finance --force
```

## Cloudflare 为什么每分钟唤醒

`cf_cron_script.js` 内有 `07:10`、`15:03`、`20:00` 等不同分钟的任务。最简单可靠的配置是给这个 Worker 设置一个 Cron Trigger：

```cron
* * * * *
```

Worker 每分钟只做一次很轻的路由匹配；没有任务时立即返回，不会运行 GitHub Actions。

Worker 使用 `event.scheduledTime` 的 UTC 时间，并在代码中转换为北京时间（UTC+8）。因此路由表全部直接写北京时间，不需要手工换算。

## Finance 当前路由

```js
"06:30_1-5": [
  {
    repo: "push",
    workflow: "finance.yml",
    inputs: { indicators: "commodity,sox" }
  }
],

"20:00": [
  { repo: "push", workflow: "finance.yml" },
  { repo: "push", workflow: "fund.yml" },
  { repo: "push", workflow: "life.yml" }
]
```

- 北京时间工作日 06:30：只生成黄金和 SOX，避免为了两个日度市场指标重跑全部宏观数据。
- 北京时间每天 20:00：Finance 未传 `indicators`，因此完整运行全部指标。
- `_1-5` 表示只在周一至周五匹配。

## Worker 如何把参数传给 GitHub

```js
body: JSON.stringify({
  ref: task.branch || DEFAULT_BRANCH,
  inputs: task.inputs || {}
})
```

06:30 会发送：

```json
{
  "ref": "main",
  "inputs": {
    "indicators": "commodity,sox"
  }
}
```

20:00 会发送：

```json
{
  "ref": "main",
  "inputs": {}
}
```

`finance.yml` 把输入写入 `FINANCE_INDICATORS`。为空时 `FinanceSource` 不筛选指标，即全量运行；有值时只保留对应指标。

## 为什么 GitHub Actions 不再设置 schedule

`finance.yml` 现在只有 `workflow_dispatch`。如果 Cloudflare 和 GitHub 都设置定时，会出现两个调度器：重复抓取、重复上传、时间难以排查。因此时钟统一放在 Cloudflare，GitHub 只接受调用。

## Cloudflare 控制台需要做什么

1. 把仓库中的 `cf_cron_script.js` 同步到现有定时 Worker。
2. 确认 Worker 的 Cron Trigger 为 `* * * * *`。
3. 在 Worker Secrets 中保留有效的 `GITHUB_TOKEN`。
4. Token 需要对 `FenLynn/push` 具有 Actions workflow 写权限。

GitHub 仓库提交不会自动替换 Cloudflare 控制台里手工部署的 Worker 代码，除非以后另建 Wrangler 自动部署流程。
