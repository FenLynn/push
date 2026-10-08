# 共享 KV 上传入口：控制台发布，不使用任何部署 CLI

## 当前交付范围

- 独立单文件 `worker.mjs`，没有第三方依赖、构建步骤或数据库。
- GitHub Actions 通过 Cloudflare Access Service Token 上传。
- Worker 再验证 Access JWT 签名、固定 issuer、AUD、有效期和机器身份；不会仅信任请求头。
- Python 客户端：`core/shared_data_client.py`，只使用标准库。
- 手动冒烟工作流：`.github/workflows/shared-data-smoke.yml`。
- **原有 Dashboard、Push 导出、旧 KV 和旧凭证均未切换。**
- 默认仅登记 `push:smoke`，写入 `v1:push:smoke:latest`，24 小时自动过期。
- 所有接口都需 Access 机器认证，没有公共读接口，没有删除/list/任意 key 操作。

## 1. 用户在 Cloudflare 上传这一个文件

1. Workers & Pages → Create application，创建独立 Worker，名称建议 `shared-data-ingest`。
2. 打开这个新 Worker 的 Edit Code。
3. 用本目录 `worker.mjs` 的**全部内容**替换默认代码，保存并发布。
4. 不要替换现有 `sci-worker`，也不要将新 Worker 连接到会调用部署 CLI 的自动构建流程。

这个单文件是直接可运行的模块 Worker，不需要 npm 安装、打包或命令行部署。
初次尚未配置 binding/变量时接口会拒绝服务，这是预期的关闭式失败。

## 2. KV binding（不是普通环境变量）

新 Worker → Bindings → Add binding → KV namespace：

| 项目 | 值 |
| --- | --- |
| Variable name | `SHARED_DATA_KV` |
| KV namespace | `SHARED_DATA_KV` |
| 核对 Namespace ID | `53d893874f7b450f9d8e54305d160f25` |

不要选择旧的 `DASHBOARD_KV`；不要新增一个叫 Namespace ID 的文本变量来代替 binding。

## 3. Worker 设置文本变量

新 Worker → Settings → Variables and Secrets（有些界面称 Environment Variables）：

| 名称 | 类型 | 值 |
| --- | --- | --- |
| `TEAM_DOMAIN` | Text | `https://fenlynn-team.cloudflareaccess.com` |
| `POLICY_AUD` | Text | `df19a23935af2f04980d9b5e8ab934520218ed7d514fdaf29a4079ca63f3ba84` |
| `INGEST_HOSTNAME` | Text | `ingest.660415.xyz` |
| `ACCESS_CLIENT_ID` | Text | 已创建的 `github-data-ingest` 服务凭证的 Client ID |

`ACCESS_CLIENT_ID` 用于进一步固定允许的机器凭证，建议设置；若不设置，仍会验证服务类型、AUD 和签名。
**Client Secret 只放 GitHub Secrets，不需要放进 Worker 或代码。**
`MODULE_REGISTRY_JSON` 暂时不设置，保持仅开放测试模块。

## 4. 域名和 Access

1. 新 Worker → Settings → Domains & Routes → Add → Custom Domain，添加 `ingest.660415.xyz`。
2. Cloudflare 自动建立 DNS 和证书；若提示域名已占用，先查原用途，不要直接覆盖旧记录。
3. 已建 Access 应用应只保护这个专用域名，Path 留空。
4. 策略必须是 `Service Auth` → Include `Service Token` → 指定 `github-data-ingest`。
5. 不使用 Bypass、Everyone 或 Any Access Service Token，不添加用户邮箱 Allow 策略。
6. 关闭这个新 Worker 的 workers.dev 和预览 URL，或同样保护所有入口。代码也会拒绝非 `INGEST_HOSTNAME` 请求并验证 JWT。

浏览器直接打开被拒绝/要求认证是预期行为。GitHub 使用机器请求头，不依赖浏览器 Cookie。
Access 应用和 Worker 都要保存/发布；只创建 Access 应用不会创建上传接口。

## 5. GitHub：先只给 Push 仓库配置

仓库 Settings → Secrets and variables → Actions：

| 类型 | 名称 | 内容 |
| --- | --- | --- |
| Secret | `CF_ACCESS_CLIENT_ID` | 同一服务凭证的 Client ID |
| Secret | `CF_ACCESS_CLIENT_SECRET` | 同一服务凭证的 Client Secret |
| Variable | `STATUS_PUSH_URL` | `https://ingest.660415.xyz/api/ingest` |

不要将凭证贴到聊天、日志、工作流 YAML 或源代码。不要删除旧 Secrets。
其他仓库以后复用同一套配置；同一凭证不能提供仓库间的安全隔离。

## 6. 手动验收

在 Push 仓库 Actions 里运行 **Shared KV: Access smoke test**：

1. 无凭证访问 `/api/health` 应被拒绝。
2. 正确凭证访问健康检查，应得到本接口 JSON，不是登录 HTML。
3. 上传一条测试快照，收到成功回执。
4. 最多等待约两分钟读取同一个 probeId，适应 KV 最终一致性。
5. Cloudflare KV Pairs 中应能看到 `v1:push:smoke:latest`；它不影响任何生产 key。

工作流只有 workflow_dispatch，没有定时或 push 触发，不会自动迁移真实数据。
冒烟测试只写一次快照（暂时故障时最多重试两次）；读回轮询最多 13 次。读取失败 404/旧版本可能是传播延迟，不等同于丢失写入。

客户端拒绝 HTTP、其他域名、URL 内凭证和重定向。401/403/登录跳转直接失败；429/临时故障和网络错误做有界退避，不打印服务凭证或错误响应正文。

## 7. 接入真实模块（冒烟通过后另行切换）

先在 Worker 的 `MODULE_REGISTRY_JSON` 登记模块与固定 key，例如：

```json
{
  "push:smoke": {"key":"v1:push:smoke:latest","repository":"FenLynn/push","expirationTtl":86400},
  "push:life": {"key":"v1:push:life:latest","repository":"FenLynn/push"},
  "academic:metrics": {"key":"v1:academic:metrics:latest","repository":"FenLynn/academic"}
}
```

不设置 expirationTtl 的正式快照不会自动过期。显式设置 registry 会替换默认登记表，需保留仍使用的模块。
每个 key 固定一个发布流程，使用 GitHub concurrency 串行发布。仓库名是审计字段，不是可信身份；共用服务凭证的仓库仍可冒充其他登记模块。

客户端调用示例（在 GitHub Actions 环境中）：

```python
from core.shared_data_client import SharedDataClient
SharedDataClient().upload('push:life', {'items': []})
```

一次上传是一个完整、非空 JSON 对象或数组，最大请求 1 MiB。禁止多仓库读改写同一个大 JSON。
`generatedAt` 是该次快照生成时间；历史日期放在 payload 内。附带 GitHub commit/run 信息，但没有 CAS 或事务，不声称可阻止所有乱序覆盖。
KV 会保留最后一次成功写入；上游失败应不上传空结果。生产模块过期提示及旧数据回退仍由消费端在切换时接入。

## 接口

| 方法 | 路径 | 操作 |
| --- | --- | --- |
| GET | `/api/health` | 验证机器认证和 binding 是否配置，无 KV 操作 |
| POST | `/api/ingest` | 校验并更新登记模块的固定 key |
| GET | `/api/status?module=push:smoke` | 读取登记模块，无写入 |

这些 URL 都受同一 Access 应用保护。Web/小程序以后由原读取 Worker 用 KV binding 消费，不向前端提供机器凭证。
`sci-worker` 这一轮未修改；现有业务读写保持原样。

## 本地验证与回退

```text
node --test tests/shared-data-ingest.test.mjs
python -m unittest tests.test_shared_data_client tests.test_dashboard_snapshot -v
```

代码只新增文件，不改现有生产逻辑。回退时停用新手动工作流/独立 Worker 即可；旧 KV、原接口和导出仍可使用。
若升级这个独立 Worker，先下载当前代码留存，再上传新版本；不要覆盖现有 Dashboard Worker。

参考：
- [Access Service Token](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)
- [验证 Access JWT](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/validating-json/)
- [服务身份 JWT 的字段](https://developers.cloudflare.com/cloudflare-one/access-controls/applications/http-apps/authorization-cookie/application-token/)
- [KV 一致性](https://developers.cloudflare.com/kv/concepts/how-kv-works/)
