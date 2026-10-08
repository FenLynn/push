# 共享 KV：URL 隐私迁移与旧记录处理

[完整接入教程](SHARED_DATA_KV.md) · [Academic 接入说明](https://github.com/FenLynn/academic/blob/main/docs/shared-data-kv.md)

## 1. 当前代码与未来日志

- 两仓库的上传 URL 只从 Actions repository **Secret** `STATUS_PUSH_URL` 注入，不回退到 Variable。
- 地址沿用自己已测试的原值，路径仍是 `/api/ingest`。不要在工作流或命令参数写明文地址，也不要填写文档中的虚构示例域名。
- 两个 Access Secrets 保持原来的同一对值；先在两个仓库创建 URL Secret，再从最新 main 运行测试，成功后删除同名旧 Variable。
- 客户端以原主机名的固定 SHA-256 指纹作精确校验，拒绝其他域名、HTTP、非 443 端口、URL 内凭证、查询、片段和重定向。指纹不是加密，不声称使公网域名不可发现。
- 文档不再发布实际上传地址，测试使用保留的虚构域名和假凭证；成功/错误诊断不打印原始 URL、Access 凭证或响应正文。
- GitHub Secret 可遮罩后续日志中的原值，但不能保证所有编码/变形都会自动遮罩；仍不能主动打印 URL、启用 `set -x` 或 dump 环境变量。
- Worker 线上 `1.0.3` 不需要为本次 GitHub 迁移重新部署。源码 `1.0.4` 不再内置域名，将来手动上传时必须保留 `INGEST_HOSTNAME`。不使用部署 CLI。

## 2. 已完成的旧 Actions 日志清理

2026-10-08，读取并核查两个仓库现有的 Shared KV 手动测试日志：Push 11 份、Academic 2 份含上传域名明文；另外两次空 URL 的失败日志没有该地址。
两个清理任务均已成功运行；已从各自日志核对到 Push 11 条、Academic 2 条成功/已不存在的回执。
按照所有者要求，两个一次性 `shared-data-log-cleanup.yml` 已从 main 移除，不再提供重复执行入口。历史运行结果保留，正常上传测试仍然只使用 `contents: read`。
当时只删除了下列固定 run IDs 的日志，没有枚举/批量删除其他任务，也没有删除运行结果、产物、KV、D1 或业务数据。

```text
Push:
37791078460 37783384665 37780621568 37776993829 37774693219
37773289508 37773244502 37771516839 37771405332 37765503320
37763578723

Academic:
37791297867 37789314748
```

清理使用当次任务短期 `GITHUB_TOKEN`，无需新 PAT/Secret。删除 workflow 不会恢复已删除的日志，也不改动 URL Secret 或 Access 凭证。

## 3. 日志删除的边界

GitHub 不支持编辑旧日志的某一行，只能删除整份运行日志，或者删除整个 run；这里仅删除日志，保留结果记录。
新增 Secret 不会让旧日志自动脱敏，也不要重跑使用 Variable 的旧提交。
以后若另有需要清理的日志，可打开对应 run → 右上角菜单 → **Delete all logs**；GitHub 页面显示可能略有变化，按 [官方日志删除说明](https://docs.github.com/en/actions/how-tos/monitor-workflows/use-workflow-run-logs#deleting-logs) 操作，不扩大上传任务权限。
已下载/转存的日志、副本和他人截图不会随 GitHub 删除而消失。

## 4. Git 历史：已经核查，但没有强推改写

当前 main 文件移除明文地址，并不等于历史清除：旧提交、这个修改提交的删除行 diff、已有 clone、fork 和 GitHub 缓存仍可能保留原值。
完整历史清理必须在暂停并发写入、备份全部改动后进行过滤与受保护的强推，然后协调所有 checkout；它会改变相关提交及后续提交的 SHA。
Academic 有其他工作区和未提交任务，共享工具又用固定 Push SHA。贸然强推可能破坏这些引用，并在旧 checkout 后续合并/推送时重新带回旧历史。

**本次不强推、不 reset、不删除分支、不改写旧提交。** 公网地址不是认证密钥，访问安全仍由 Access 与 Worker 校验提供；为隐藏非凭证 URL 重写两个仓库历史的收益有限。
如果所有者仍要求重写，需要单独确认风险与停写窗口，清理 Push 后更新 Academic 的固定工具 SHA，再重建/安全迁移其他 checkout。不能承诺抹除他人副本或公开缓存。

依据：[GitHub 历史清理风险与限制](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/removing-sensitive-data-from-a-repository)、[删除日志 API](https://docs.github.com/en/rest/actions/workflow-runs#delete-workflow-run-logs)、[Secret 的用法与遮罩](https://docs.github.com/en/actions/how-tos/write-workflows/choose-what-workflows-do/use-secrets)。
