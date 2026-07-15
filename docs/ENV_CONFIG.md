# 环境配置

项目通过环境变量读取运行密钥和服务配置，仓库中只保存变量名称，不保存真实值。

## GitHub Actions

在仓库的 Actions secrets 中配置 `PUSH_ENV_FILE`，内容采用 `.env` 格式。工作流运行时会将其临时加载到 Runner 环境，任务结束后由 Runner 清理。

示例：

```dotenv
PUSHPLUS_TOKEN=
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_D1_DATABASE_ID=
CLOUDFLARE_D1_API_TOKEN=
R2_ACCOUNT_ID=
R2_ACCESS_KEY=
R2_SECRET_KEY=
R2_BUCKET_NAME=push-service
PUSH_R2_PUBLIC_BASE_URL=https://whoisyourdaddyqywx-worker.660415.xyz/api/public/push-assets
```

`PUSH_R2_PUBLIC_BASE_URL` 是图片外链前缀。图片只写入 R2，并使用
`finance/<indicator>/latest.png` 等稳定对象名覆盖更新；URL 会自动附加内容哈希，
因此不会因为 CDN 缓存显示旧图，也不会按日期无限增长。

Finance 与 Estate 的结构化数据写入同一个 D1：日频金融数据保留 2 年，
日频房产数据保留 3 年，超期前聚合为月度数据；官方月度/季度序列长期保留。

请在 GitHub Secrets 中填写真实值，不要把填写后的文件提交到仓库。

## 本地运行

在项目根目录创建 `.env`：

```dotenv
RUN_MODE=local
PUSHPLUS_TOKEN=
```

`.env` 已被 `.gitignore` 排除。提交前仍应执行：

```bash
git status --short
git check-ignore -v .env
```

如密钥曾经进入提交历史，仅删除当前文件不足以消除泄露风险；应轮换密钥并清理 Git 历史。
