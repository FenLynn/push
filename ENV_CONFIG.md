# 环境自动检测系统使用指南

## 🎯 功能说明

系统会根据**主机名**或**IP地址**自动识别运行环境，并加载对应的配置文件，无需手动修改代码。

### 支持的环境

| 环境 | 识别条件 | TTR RSS 地址 | 代理设置 |
|------|---------|-------------|---------|
| **local** | 主机名: `py`, `localhost`<br>或 IP: `192.168.*` | `http://192.168.12.21:1040` | 无代理 |
| **aliyun** | 主机名: `iZ*`, `aliyun`<br>或 IP: `47.*`, `8.*` | `http://47.109.56.199:12002` | 可选 |
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
1. **环境变量** (如 `PUSHPLUS_TOKEN`, `TTRSS_PASSWORD`)
2. **环境特定配置** (`local.yaml`, `aliyun.yaml`)
3. **默认配置** (`default.yaml`)

---

## 🔧 配置示例

### default.yaml (通用配置)
```yaml
network:
  ttrss_url: "http://47.109.56.199:12002"  # 默认远程
  ttrss_username: "admin"
  pushplus_token: "${PUSHPLUS_TOKEN}"  # 从环境变量读取
```

### local.yaml (仅需要覆盖的部分)
```yaml
network:
  ttrss_url: "http://192.168.12.21:1040"  # 本地 TTR RSS
  # 其他配置继承 default.yaml
```

---

## 🚀 使用方法

### 1. 自动检测（推荐）

直接运行，系统自动识别环境：

```bash
cd /nfs/python/push
conda run -n py39 python test_paper.py
```

**控制台输出**：
```
[Config] Detected environment: local
[Paper] Connecting to TTR RSS: http://192.168.12.21:1040
```

### 2. 手动指定环境

如果自动检测不准确，可以手动指定：

```bash
export PUSH_ENV=local    # 强制使用 local 环境
conda run -n py39 python test_paper.py
```

```bash
export PUSH_ENV=aliyun   # 强制使用 aliyun 环境
conda run -n py39 python test_paper.py
```

### 3. 设置敏感信息（环境变量）

```bash
# 设置 TTR RSS 密码
export TTRSS_PASSWORD="your_password_here"

# 设置 PushPlus Token
export PUSHPLUS_TOKEN="bb703a31058442b3a61489b82eaf1d63"

# 如果需要代理
export HTTP_PROXY="http://proxy.com:8080"
```

---

## 📝 在代码中使用

### Paper 模块（已集成）

```python
from core.env import get_env_config

class PaperSource:
    def _login(self):
        env_config = get_env_config()
        
        url = env_config.get('network', 'ttrss_url')
        username = env_config.get('network', 'ttrss_username')
        password = env_config.get('network', 'ttrss_password')
        
        client = TTRClient(url, username, password)
```

### 在其他模块中使用

```python
from core.env import get_env_config

config = get_env_config()

# 获取配置
token = config.get('network', 'pushplus_token')
url = config.get('github', 'owner')

# 设置代理（如果配置中有）
config.set_proxy()
```

---

## 🔍 检测逻辑

```python
from core.env import EnvironmentDetector

# 手动检测
env = EnvironmentDetector.detect()
print(f"Current environment: {env}")
```

**检测规则** (按顺序):
1. 环境变量 `PUSH_ENV` (最高优先级)
2. 主机名匹配
3. IP 地址匹配
4. 默认为 `unknown`

---

## ✅ 测试环境检测

```bash
cd /nfs/python/push
conda run -n py39 python core/env.py
```

**预期输出**（在 py 主机上）：
```
[Config] Detected environment: local
Environment: local
TTR RSS URL: http://192.168.12.21:1040
TTR RSS Username: admin
```

---

## 🆕 添加新环境

假设要添加 `aws` 环境：

### 1. 创建 `cloud/config/aws.yaml`：
```yaml
network:
  ttrss_url: "http://aws-server.example.com:12002"
  http_proxy: "http://aws-proxy:8080"
```

### 2. 修改 `core/env.py` 添加识别规则：
```python
ENV_RULES = {
    'local': {...},
    'aliyun': {...},
    'aws': {  # 新增
        'hostnames': ['ip-*', 'aws'],
        'ip_prefixes': ['3.', '52.']  # AWS IP 段
    }
}
```

---

## 📌 注意事项

1. **敏感信息**：密码/Token 必须通过环境变量设置，不要写在 YAML 文件中
2. **配置继承**：环境配置只需写与 default.yaml 不同的部分
3. **IP 检测**：如果主机有多个 IP，优先使用默认路由的 IP
4. **测试建议**：先用 Mock Channel 测试，再用真实 Channel

---

## 🐛 故障排查

### 问题：无法连接 TTR RSS

**检查环境检测**：
```bash
conda run -n py39 python core/env.py
```

**检查密码环境变量**：
```bash
echo $TTRSS_PASSWORD
```

### 问题：使用了错误的环境

**手动指定**：
```bash
export PUSH_ENV=local
```

### 问题：配置未生效

**检查 YAML 语法**：
```bash
conda run -n py39 python -c "import yaml; yaml.safe_load(open('cloud/config/local.yaml'))"
```
