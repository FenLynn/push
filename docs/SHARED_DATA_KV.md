# 共享 KV：GitHub 上传与其他仓库接入

[项目首页](../README.md) · [Worker 控制台配置与故障排查](../services/shared-data-ingest/README.md)

## 1. 当前状态与边界

2026-10-08，Push 的四阶段测试已在线通过 Worker `1.0.3`：匿名拒绝、机器认证/验签、临时快照上传、相同 probeId 读回。
Academic 新增独立的手动示例，**需先登记 `academic:smoke`，尚不代表 Academic 在线测试已通过**。

```text
GitHub 任务生成 JSON
  → HTTPS + Access Service Token
  → ingest.660415.xyz（专用 Service Auth 应用）
  → shared-data-ingest（再次验证 JWT、校验模块登记表）
  → SHARED_DATA_KV 中该模块自己的 key
```

- 不直接调用 Cloudflare KV REST API，不给 GitHub 分发 Cloudflare 账户 API Token。
- 不使用任何部署 CLI；Worker 代码/变量只能由所有者在 Cloudflare 控制台保存并 Deploy。
- 不修改现有 Push 生产任务、D1/R2、Dashboard 或 Academic 数据生成流程；新增示例只有 `workflow_dispatch`。
- 当前统一凭证就是 Access 的 **Client ID + Client Secret**，不是 GitHub 登录、邮箱 OTP 或浏览器 Cookie；目前没有额外 `STATUS_PUSH_TOKEN`/Bearer 自定义凭证。
- GitHub 任务的 `GITHUB_TOKEN` 仅用于读取代码，与 Access 凭证不同。此上传流程不需要 GitHub 写权限或新增 PAT。

## 2. 各仓库分别配置三项

在 **每一个调用仓库**的 Settings → Secrets and variables → Actions 配置：

| 类型 | 名称 | 内容/来源 |
| --- | --- | --- |
| Secret | `CF_ACCESS_CLIENT_ID` | 已创建的 `github-data-ingest` 服务凭证完整 Client ID，通常以 `.access` 结尾 |
| Secret | `CF_ACCESS_CLIENT_SECRET` | 同一个 Service Token 的 Client Secret；只通过 GitHub Secrets 配置 |
| Variable | `STATUS_PUSH_URL` | `https://ingest.660415.xyz/api/ingest` |

Push 中的 Secrets 不会自动传到 Academic；代码 checkout 也不会继承另一仓库的 Secrets。个人账号的多个仓库需分别填写同一套值；若以后使用组织 Secrets，必须明确允许相应仓库访问。
本示例不声明 GitHub Environment，所以只填 Environment Secrets 而未关联 Environment，也会得到空值。

这些配置与旧 `PUSH_ENV_FILE` 无关。保留旧 Secrets，不将密钥写到 YAML、文档、JSON payload、终端参数或日志，不开启会输出命令/变量的 `set -x`。
Service Token 到期或轮换时同步更新所有调用仓库；不要把 Secret 发到聊天。AUD 和 KV Namespace ID 不是凭证。

## 3. Academic 首次测试：登记模块

现有 Worker `1.0.3` 已支持环境变量登记表，不需要改代码/再上传新版本。
Cloudflare → Workers & Pages → `shared-data-ingest` → Settings → Variables and Secrets，新增 **Text** 变量 `MODULE_REGISTRY_JSON`。
若目前仍使用默认登记表，仅两个测试模块时填：

```json
{
  "push:smoke": {
    "key": "v1:push:smoke:latest",
    "repository": "FenLynn/push",
    "expirationTtl": 86400
  },
  "academic:smoke": {
    "key": "v1:academic:smoke:latest",
    "repository": "FenLynn/academic",
    "expirationTtl": 86400
  }
}
```

**若已有 `MODULE_REGISTRY_JSON`，只合并新增 Academic 条目，保留每个已有条目。** 环境变量会替换整个默认表，不会自动合并；删除 `push:smoke` 会使原测试报 `unknown_module`。每个模块必须使用不同 key。
保存并 **Deploy** 使配置生效；只 Save version 不保证启用。KV binding、Access 策略、TEAM_DOMAIN、POLICY_AUD、ACCESS_CLIENT_ID 均保持原值。
测试 key 有效期 24 小时，重新测试刷新有效期；不删除、不改写生产 key。

## 4. 运行测试

| 仓库 | Actions 工作流 | 模块 | key |
| --- | --- | --- | --- |
| Push | Shared KV: Access smoke test | `push:smoke` | `v1:push:smoke:latest` |
| Academic | Shared KV: Academic example | `academic:smoke` | `v1:academic:smoke:latest` |

点 Run workflow → 最新 `main`，不要重跑旧提交。Academic workflow 从 Push **固定的 40 位提交 SHA** 稀疏 checkout 上传工具，不跟随 `main` 自动漂移，不复制第二套客户端。
它保留调用方 Academic 的 GitHub metadata，不会把工具仓库 Push 当成数据来源。

四步预期：

1. 无凭证 GET `/api/health` 返回 302/401/403；这一步的 403 是正常结果，不写 KV。
2. 带机器凭证得到服务 JSON 与版本；验证 JWT，不操作 KV。
3. POST 一条带随机 probeId 的临时快照。
4. 最多 13 次 GET、每次间隔 10 秒确认相同 payload，适应 KV 最终一致性。

每次测试只有一条逻辑快照，暂时故障最多重试两次；不能承诺网络超时后服务端绝对没有完成写入。
同仓库同测试使用 `concurrency` 排队；不同仓库写不同 key，不互相覆盖。

## 5. 其他任务如何模仿

固定流程：**登记独立模块 → 生成/检查 JSON → 上传一次快照**。上传本身不会运行抓取、生成网站或改 GitHub 文件。

### Push 自己的任务

完成业务数据生成后，把纯 payload 保存成 UTF-8 JSON，例如 `artifacts/life.json`，然后增加一个上传步骤：

```yaml
- name: Publish validated snapshot
  # 只在上游生成和质量检查成功后执行，不使用 always()。
  env:
    STATUS_PUSH_URL: ${{ vars.STATUS_PUSH_URL }}
    CF_ACCESS_CLIENT_ID: ${{ secrets.CF_ACCESS_CLIENT_ID }}
    CF_ACCESS_CLIENT_SECRET: ${{ secrets.CF_ACCESS_CLIENT_SECRET }}
  run: python scripts/shared_data_publish.py --module push:life --file artifacts/life.json
```

`push:life` 是**接入模板，不是已开放生产模块**。先在 Worker 现有登记表里合并：

```json
"push:life": {"key": "v1:push:life:latest", "repository": "FenLynn/push"}
```

### Academic 或其他仓库

模仿 [Academic 的实际工作流](https://github.com/FenLynn/academic/blob/main/.github/workflows/shared-data-smoke.yml)：

1. 只读 checkout 调用仓库，生成业务 JSON。
2. 用固定审核过的 Push commit checkout `core/shared_data_client.py` 和 `scripts/shared_data_publish.py` 到 `.shared-kv-toolkit`（稀疏 checkout，`persist-credentials: false`）。
3. 在调用仓库上下文执行：

```yaml
- name: Publish validated Academic snapshot
  env:
    STATUS_PUSH_URL: ${{ vars.STATUS_PUSH_URL }}
    CF_ACCESS_CLIENT_ID: ${{ secrets.CF_ACCESS_CLIENT_ID }}
    CF_ACCESS_CLIENT_SECRET: ${{ secrets.CF_ACCESS_CLIENT_SECRET }}
  run: python .shared-kv-toolkit/scripts/shared_data_publish.py --module academic:metrics --file artifacts/metrics.json
```

事先在登记表合并 `academic:metrics` → `v1:academic:metrics:latest` / `FenLynn/academic`。
Node、Python、Shell 等任务都可输出 JSON，再调用同一个 Python 上传器；Runner 需 Python 3.12，不需要 pip 安装依赖。
升级共享工具时只审核并更新 workflow 的固定 Push SHA；不要改成浮动 ref，不在运行中下载/执行未固定的脚本。

同一个 key 只交给一个生产者/一个串行发布队列管理；避免多个独立 workflow 同时写。KV 没有本接口的 CAS/事务，队列和时间戳不保证绝对防止跨生产者乱序覆盖。

生产上传器只 POST，不健康探测、不读回、不 list、不触碰 D1，避免每次发布产生额外读/列表压力。
认证类 401/403 不重试；网络错误、429/500/502/503/504 最多三次，遇短暂故障有界退避。

## 6. 协议与数据要求

上传器将纯 payload 包成：

```json
{
  "schemaVersion": 1,
  "module": "academic:metrics",
  "generatedAt": "2026-10-08T13:00:00Z",
  "source": {
    "repository": "FenLynn/academic",
    "commit": "调用仓库的40位提交SHA",
    "runId": "调用方Actions运行ID"
  },
  "payload": {"count": 44, "items": []}
}
```

上面 `commit` 的中文说明是占位说明；实际由 GitHub 环境变量生成合法值，不手写。
请求上限 **1 MiB（含 envelope）**；payload 须为非空对象/数组、标准 JSON，不含 NaN/Infinity。`--file` 只传 payload，不重复包装 envelope。
`receivedAt` 由 Worker 添加。`generatedAt` 是此次快照生成的 UTC 时间，历史数据时间放在 payload。
来源信息记录调用仓库 SHA/run，而不是工具 checkout SHA。

生产者还必须检查业务完整性/合理数量；上传器不会判断科学数据质量，`{"items":[]}` 形式合法但不必然适合覆盖旧数据。
上游失败/结果不完整就不执行上传，保留最后一次成功快照；不要用异常信息、Cookie、稿件后台数据、未公开审稿意见或密钥作为 payload。

## 7. 安全、读取与长期限制

- `*.660415.xyz` 的网页登录保护保留；专用 `ingest` 应用绑定指定 Service Auth 凭证，不把机器 token 放进泛域名全站 Allow、不设 Bypass/Everyone。
- 收到错误先辨别 Access/WAF/Worker 层；不能为了测试通过而关闭 JWT 验签、issuer、AUD 或时效检查。
- 模块登记表拒绝任意 key，`source.repository` 需匹配登记，但它不是密码学证明。**共享机器凭证不隔离仓库**：持有同一凭证的受信任仓库技术上可冒充另一已登记来源。需要隔离时再换成每仓库独立凭证/身份。
- Worker KV binding 本身不提供代码层的只读权限；“只读”指读取端没有写入口/写逻辑，不是 Cloudflare 为该 binding 自动颁发只读身份。
- 目前 `/api/status` 也需机器认证，没有公共读取 API。Web/小程序将来通过自己的后端 binding 读 KV，绝不向前端分发机器凭证。
- KV 是最终一致性存储，不适合即时计数、余额、锁或必须强一致的数据；本方案用于低频状态/快照，不替换 D1 的历史结构化数据。
- 无 TTL 的正式快照长期保留，但可能变陈旧；消费端以后按 `generatedAt/receivedAt` 提示新鲜度。测试条目才默认 24 小时过期。

## 8. 排错与回退

| 日志 | 处理 |
| --- | --- |
| `missing_access_credentials` | 检查**当前调用仓库**的两项 Secrets，别只看 Push；Environment Secrets 需关联 Environment |
| `invalid_upload_url` | URL 应为完整 HTTPS `/api/ingest`，不含 Markdown 括号、引号、查询串或尾部其他路径 |
| `layer=access` | 检查专用应用 Service Auth、选中同一 Service Token、成对 ID/Secret |
| `layer=cloudflare_html` / `cloudflare_bic` | 根据 Ray ID 查 Security Events，不能仅凭 403 断定 Access 凭证过期 |
| `unknown_module` | 登记对应模块并 Deploy；保留其他登记条目，不改用 Push 的测试 key |
| `invalid_source` | 登记仓库与调用方 `GITHUB_REPOSITORY` 不一致；别手写 Push metadata 冒充 Academic |
| `invalid_access_token` | 按 `auth_reason` 定位；旧部署先升级到已验证 `1.0.3`，不绕过认证 |
| `access_keys_unavailable` | JWKS 获取/导入失败；`1.0.3` 已修复 Workers 不支持 `redirect:error` 的代码问题 |
| `configuration_error` | 查 binding 或登记表 JSON 是否完整/重复 key，不删除原表盲试 |
| `read_back_timeout_kv_eventual_consistency` | 写回执已成功，但传播/并发等问题尚未确认；检查同 key 是否有第二个生产者，不直接认定写入丢失 |

停用新 workflow 或删除新增发布步骤即可停止写入，旧任务继续运行。回退工具改回旧固定 SHA；回退登记表只移除新增条目，保留其他模块。
登记表更新前保存原值，Worker 升级前备份原代码；测试不要求覆盖任何现有生产文件或数据。

本地回归（无真实凭证、无网络写入）：

```text
python -m unittest tests.test_shared_data_client tests.test_shared_data_publish tests.test_dashboard_snapshot
node --test tests/shared-data-ingest.test.mjs
workerd test tests/shared-data-ingest.workerd.capnp
```

最后一行是**独立 workerd 本地运行时**，不是部署命令；无需为本方案安装/使用任何部署 CLI。

参考：[GitHub Secrets 的作用域](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)、[Access Service Token](https://developers.cloudflare.com/cloudflare-one/access-controls/service-credentials/service-tokens/)、[KV 一致性](https://developers.cloudflare.com/kv/concepts/how-kv-works/)。
