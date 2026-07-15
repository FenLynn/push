# 环境配置

项目通过环境变量读取运行密钥和服务配置，仓库中只保存变量名称，不保存真实值。

## GitHub Actions

在仓库的 Actions secrets 中配置 `PUSH_ENV_FILE`，内容采用 `.env` 格式。工作流运行时会将其临时加载到 Runner 环境，任务结束后由 Runner 清理。

示例：

```dotenv
PUSHPLUS_TOKEN=
SMMS_TOKEN=
SEE_TOKEN=
CLOUDFLARE_ACCOUNT_ID=
CLOUDFLARE_D1_DATABASE_ID=
CLOUDFLARE_D1_API_TOKEN=
```

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
