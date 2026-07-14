# Life 数据源维护说明

## 输出

`LifeSource` 将电影、剧集、综艺和图书榜单写入 `dashboard:snapshot:life:latest`，供 `sci-worker -> qywx-worker -> qywx-miniapp` 只读使用。

## 数据源与降级

- 今日电影：优先读取公开的全国电影日榜页面；失败后再尝试 AKShare 票房接口，最后降级为豆瓣在映列表。
- 年度电影：使用 AKShare 对应的艺恩年度票房接口。该上游目前可能返回空响应，系统不会用热门榜冒充年度榜。
- 剧集、综艺：优先 AKShare，失败后读取对应的豆瓣公开集合。
- 热门、高分电影和图书：读取豆瓣公开页面或公开集合。

当某个上游短时失败时，系统可复用最近一次有效 KV 快照：年度电影最多 14 天，其余榜单最多 3 天。超过期限后返回空数据，并由小程序显示明确原因。

## 已知边界

- 榜单是轻量参考信息，不是校勘或行业结算数据。
- 年度票房上游失效属于外部接口问题；当前按“空缺但不误标”处理，不列为程序故障。
- 调试可运行 `python -m unittest tests.test_dashboard_snapshot`，并单独调用 `LifeSource()._get_public_movie_daily()` 检查今日榜。
