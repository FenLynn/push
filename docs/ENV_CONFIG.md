# 环境自动检测系统使用指南

## 🎯 功能说明

系统会根据**主机名**或**IP地址**自动识别运行环境，并加载对应的配置文件，无需手动修改代码。

### 支持的环境

| 环境 | 识别条件 | 适用场景 | 代理设置 |
|------|---------|---------|---------|
| **local** | 主机名: `py`, `localhost`<br>或 IP: `192.168.*` | 开发机、本地测试 | 无代理 |
| **aliyun** | 主机名: `iZ*`, `aliyun`<br>或 IP: `47.*`, `8.*` | 云服务器、生产环境 | 可选 |
| **unknown** | 其他情况 | 使用 default.yaml | 默认配置 |

---

## 📁 配置文件结构

```
cloud/config/
├── default.yaml    # 默认配置（通用设置）
├── local.yaml      # Local 环境覆盖配置
└── aliyun.yaml     # Aliyun 环境覆盖配置
```

**配置优先级** (从高到低)：
1. **环境变量** (如 `PUSHPLUS_TOKEN`, `CLOUDFLARE_D1_API_TOKEN`)
2. **环境特定配置** (`local.yaml`, `aliyun.yaml`)
3. **默认配置** (`default.yaml`)

---

## 🔧 配置示例

### default.yaml (通用配置)
```yaml
network:
  pushplus_token: "${PUSHPLUS_TOKEN}"  # 从环境变量读取
```

---

## 🚀 使用方法

### 1. 自动检测（推荐）

直接运行，系统自动识别环境：

```bash
cd /nfs/python/push
python main.py run morning
```

**控制台输出**：
```bash
[Config] Detected environment: local
```

### 2. 手动指定环境

如果自动检测不准确，可以手动指定：

```bash
export PUSH_ENV=local    # 强制使用 local 环境
python main.py run paper
```

### 3. 设置敏感信息（环境变量）

```bash
# 设置 PushPlus Token
export PUSHPLUS_TOKEN="bb703a31058442b3a61489b82eaf1d63"

# 设置 Cloudflare D1 (Paper 模块必需)
export CLOUDFLARE_D1_API_TOKEN="..."
export CLOUDFLARE_D1_ACCOUNT_ID="..."
export CLOUDFLARE_D1_DATABASE_ID="..."
```

---

## 📝 在代码中使用

### 获取配置

```python
from core.env import get_env_config

config = get_env_config()

# 获取配置
token = config.get('network', 'pushplus_token')
r2_id = config.get('cloudflare', 'r2_account_id')

# 设置代理（如果配置中有）
config.set_proxy()
```

---

## 📌 注意事项

1. **敏感信息**：密码/Token 必须通过环境变量设置或 `.env` 文件，不要写在 YAML 文件中。
2. **已经移除 TTRSS**：所有关于 `ttrss_url` 或 `ttrss_password` 的配置均已废弃。
3. **Paper 模式**：Paper 模块现在优先通过 `PAPER_SOURCE_MODE=d1` 运行。
