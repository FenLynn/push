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

### 403 排查：先辨别拒绝发生在哪一层

新版日志会报告 `Failed stage`，以及有限、经过校验的诊断字段；不输出响应正文、JWT、Client ID 或 Client Secret。

- `layer=access, response=html` 或 `response=json`：响应具有本域名的 Access 标识。Access 可根据请求的 Accept 返回 HTML 或 JSON；优先检查机器凭证是否配对、Service Auth 策略的具体 Include/Require/Exclude 条件。
- `layer=worker, worker_error=...`：收到已知的 Worker JSON 错误码，检查 Worker 的 AUD、TEAM_DOMAIN、ACCESS_CLIENT_ID 或对应错误。不关闭 Access 来绕过二次校验。
- `layer=cloudflare_html` 或 `layer=unknown`：还不能判断具体拦截者，结合安全事件/Access 记录及安全格式的 `cf_ray` 定位。
- `layer=cloudflare_bic, edge_error_code=1010`：Browser Integrity Check 拒绝了客户端标识。客户端所有请求（含匿名检查）统一发送真实的 `SCI-SharedKV/1.0` User-Agent，不再使用默认 Python-urllib 标识，也不伪装浏览器。不要直接关闭全站安全设置。

Worker 的 Live 日志与 Access 认证日志是不同来源。在 Access 层被拦截的请求通常不会调用 Worker。Live 应先开启再运行测试，空 Live 本身不构成请求位置的完整证明。
服务凭证属于非用户身份认证；普通 Access 用户登录日志未必显示这类记录，不能只凭其为空判定未发出请求。
具体 `ingest.660415.xyz` 应用通常优先于 `*.660415.xyz` 通配应用，不要直接删掉其他网页的登录保护。

客户端源码更新后，请在 Actions 点击 **Run workflow**，选择最新 **main** 发起新测试，不要只重跑旧提交的测试记录。

### Worker v1.0.3：公钥加载修复与 JWT 拒绝诊断

**这次需要在 Cloudflare Edit Code 手动替换整个 `worker.mjs` 并发布**，仅更新 GitHub 客户端不会改变已部署的 Worker。先下载旧代码作为回退；binding、域名、Access 策略保持不变，不使用任何部署 CLI。

旧版把多个 JWT 校验失败归入同一个 `invalid_access_token`，不能仅凭它断定 Cookie/Token 过期、Client Secret 错误或签名有问题。新版继续拒绝全部不合法请求，仅在错误 JSON 中添加固定的 `authReason` 枚举，客户端以 `auth_reason` 显示，不输出 JWT、原始 claims、配置值或凭证。

| `auth_reason` | 下一步只核对这一项 |
| --- | --- |
| `issuer_mismatch` | Worker `TEAM_DOMAIN` 与实际 Access 团队 HTTPS 域名 |
| `audience_mismatch` | 先看下方两个脱敏比对结果，区分生效配置不同与 JWT 来自另一应用，不直接认定 AUD 填错 |
| `client_id_mismatch` | Worker `ACCESS_CLIENT_ID` 与 GitHub `CF_ACCESS_CLIENT_ID` 一致；是完整 `.access` ID，不是 `github-data-ingest` 名称或 Secret |
| `service_identity_mismatch` / `token_type_mismatch` | 是否收到官方服务身份 JWT；不能以放弃校验作为修复 |
| `expired_token` / `token_not_yet_valid` / `invalid_token_time` | 有效期、复用的 assertion 或运行时钟 |
| `unknown_signing_key` / `signature_mismatch` | 团队公钥/密钥轮换与签名；不能跳过验签 |
| `malformed_token` / `unsupported_header` / `token_too_large` | assertion 的结构、算法或大小 |

健康检查成功将显示版本 `1.0.3`；所有 JWT 诊断路径仍不读取/写入 KV 或 D1。

v1.0.3 修复公钥请求的 Workers 运行时兼容问题：`workerd` 不支持 `redirect: "error"`，会在发出网络请求前抛 `TypeError`，旧代码捕获后只显示 `access_keys_unavailable`。现改为 `redirect: "manual"`，且所有非 2xx（包括全部 3xx）仍直接拒绝，不跟随重定向、不信任重定向响应中的公钥。团队、AUD、有效期、机器身份与签名校验均保持不变。

新增本地运行时回归 `tests/shared-data-ingest.workerd.capnp` / `.mjs`，可直接用独立 `workerd` 二进制的 `test` 命令运行，不使用部署 CLI。测试不监听端口、不联网、不含真实凭证、仅使用本地生成的 RSA 密钥和内存存储；已复现旧版返回 503，并验证修正版通过字符串/数组 AUD 验签、拒绝伪造签名/错误 AUD/公钥重定向。

运行时实现依据：[Cloudflare workerd Request 的重定向解析](https://github.com/cloudflare/workerd/blob/main/src/workerd/api/http.c%2B%2B)。应同时保留 Node 单元测试和真实运行时回归，避免两种环境差异被 mock 隐藏。

v1.0.2 按 RFC 7519 §4.1.3 接受 `aud` 的单字符串和字符串数组两种标准形式，仍要求精确等于/包含配置 AUD，不做子串、前缀或大小写宽松匹配。旧版只接受数组，并把合法字符串错误归为 `audience_mismatch`；这是兼容性缺口，但不能仅凭旧日志断定现网收到的就是字符串。

对已通过签名验证、但 AUD 不匹配的请求，Worker 仅返回应用 ID 的 SHA-256 指纹及字段形状。冒烟脚本使用所有者提供、且已从 Access 响应头核对过的公开 ingest AUD 作诊断参考，客户端不打印指纹，只显示：

- `worker_aud_matches_expected=False`：线上 Worker 的配置不等于参考 AUD，核查活动部署版本，而不是只看编辑弹窗。
- `worker_aud_matches_expected=True` 且 `jwt_aud_matches_expected=False`：配置正确，但验签后的 JWT 指向另一应用；核查额外 Worker Access 保护与重叠应用，不要盲目替换正确值。
- `aud_shape=string/array/missing/other`：实际 JWT 的 AUD 字段形式。格式不合法时为 `invalid_audience_format`，不再混同数值不匹配。

诊断参考值只用于比对，不是认证授权依据；真正的允许/拒绝仍由 Worker 的配置、精确 AUD 校验、机器身份、有效期与签名共同决定。若将来重建 Access 应用，只更新公开参考值和 Worker 配置，不将服务凭证写入代码。

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
- [Access 应用匹配与策略继承](https://developers.cloudflare.com/cloudflare-one/access-controls/policies/app-paths/)
- [Access 认证日志](https://developers.cloudflare.com/cloudflare-one/insights/logs/dashboard-logs/access-authentication-logs/)
- [Cloudflare 1010 与 Browser Integrity Check](https://developers.cloudflare.com/support/troubleshooting/http-status-codes/cloudflare-1xxx-errors/error-1010/)
- [RFC 7519 Audience 字段的两种形式](https://datatracker.ietf.org/doc/html/rfc7519#section-4.1.3)
