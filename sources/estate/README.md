# Estate 数据源维护说明

## 输出

`EstateSource` 汇总成都和西安的轻量房产指标，写入固定 KV 键
`dashboard:snapshot:estate:latest`。每次成功抓取会覆盖同一个快照，不会按日期累积 KV 垃圾。

## 当前来源

### 成都

- 来源：成都市住建蓉 e 办公开的“商品房当日成交”接口。
- 旧地址 `www.cdzjryb.com/SCXX/Default.aspx?action=ucEveryday2` 已迁移到 SPA，不能再解析 HTML 表格。
- 当前适配器复现 SPA 的公开网关请求：先读取服务器时间，再使用页面公开的 HMAC-MD5 规则生成一次性请求头，最后读取当天全市汇总。
- 输出新房与存量房的住宅成交套数和住宅成交面积。
- 不使用账号、Cookie 或浏览器登录态。

### 西安

- 来源：房天下西安移动端公开二手房住宅列表页。
- 当前只输出二手房挂牌总量，不将其伪装成成交量。
- 内部分类键暂时保留 `SecondHand_Count_Anjuke`，用于延续既有 D1 历史曲线；快照中的
  `source` 会明确标记为 `fang-mobile`。
- 页面结构变化时应独立修改西安适配器，不要影响成都链路。

## 降级规则

单个城市当天抓取失败时，只复用 KV 中 7 天内该城市最后一次有效数据，并保留原始
`sourceDate`、标记 `stale: true`。超过 7 天不再展示旧值，也不会把旧值写成当天 D1 记录。

成都和西安是两条独立适配器。维护其中一个来源时，必须分别验证另一来源仍能抓取，并运行
`tests/test_dashboard_snapshot.py`。
