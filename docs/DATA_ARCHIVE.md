# Finance / Estate 数据归档

## 数据链路

```text
GitHub Actions (push)
  -> 采集并校验 Finance / Estate
  -> D1: data_series + data_observations
  -> R2: finance/<indicator>/latest.png
  -> sci-worker: 通过受保护的 REST Secret 查询跨账号 D1
  -> qywx-worker: 小程序鉴权代理、签名读取跨账号 R2
  -> qywx-miniapp: 长期数据页面
```

没有新增 DataHub 或额外数据库。`push-estate` D1 是唯一结构化归档库，
`push-service` R2 是 Push 文件的唯一对象存储。

## 可信数据边界

- Finance 仅将 CPI、PPI、PMI、GDP、M2、LPR、SHIBOR、国债、汇率和全国房地产景气指数写入长期库。
- 随机数据、固定默认值和代理拼接指标默认停用。临时排障时可设置
  `FINANCE_ENABLE_EXPERIMENTAL=true`，但这些指标仍不会自动进入长期库。
- Estate 的长期主序列为成都、西安 70 城月度新房/二手房价格指数。
- 成都日成交保留为补充序列；西安网页挂牌量因历史统计口径突变，不写入长期趋势库。

## 留存规则

| 数据 | 留存 |
| --- | --- |
| Finance 日频 | 730 天，超期前聚合为月度均值 |
| Estate 日频 | 1095 天，超期前聚合为月度均值 |
| 官方月度/季度 | 长期保留 |
| 采集运行记录 | 90 天 |
| `system_logs` | 30 天 |
| qywx events / audit / jobs | 14 / 30 / 90 天 |
| 过期 qywx sessions | 自动删除 |

去重状态（例如论文推送判重表）不参与滚动清理。

## R2 滚动对象

- 图表：`finance/<indicator>/latest.png`
- 通用图片：`images/<module>/<filename>`
- 报告：`output/<module>/latest.html`（不通过公开图片代理提供）

每次上传覆盖同一个对象，并在公开 URL 后附加内容哈希 `?v=<sha256>`。
上传成功后会清除该指标或报告目录内的旧日期对象。

公开图片由 qywx-worker 的 `/api/public/push-assets/*` 提供。qywx-worker
使用 `aws4fetch` 在服务端签名读取 A 账号的私有 R2；访问密钥只保存为
Worker Secret，浏览器和小程序不会接触。R2 bucket 本身不需要开启公共访问。

## API

- `GET /api/miniprogram/finance/macro`
- `GET /api/miniprogram/finance/macro/series?id=...&resolution=monthly`
- `GET /api/miniprogram/estate`
- `GET /api/miniprogram/estate/series?id=...&resolution=monthly`

四个接口均要求有效的小程序会话。图片代理是公开只读接口，只允许
`finance/`、`estate/`、`images/` 下的图片扩展名。

## 启用顺序

1. 为 sci-worker 配置 `PUSH_D1_API_TOKEN` Secret 并部署。
2. 为 qywx-worker 配置 `PUSH_R2_ACCESS_KEY_ID`、`PUSH_R2_SECRET_ACCESS_KEY`
   Secrets 并部署公开图片代理。
3. 运行一次 `push` 的 Estate 与 Finance workflows，初始化 D1 并回填数据。
4. 在微信开发者工具上传 qywx-miniapp，新页面入口位于金融页“宏观”和房产简报“长期趋势”。

Finance 工作日 09:25、Estate 工作日 18:35（北京时间）会自动采集，
同时保留手工 `workflow_dispatch`。
