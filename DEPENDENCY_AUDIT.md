# Dependencies Audit Report (Updated)

## 检查时间
2026-02-13 04:05

## 核心依赖 (requirements.txt)
我们对依赖进行了精简，移除了不再需要的 TTRSS 相关包，并添加了云原生架构所需的包。

### ✅ 保留与新增的核心依赖
| 包名 | 最新要求 | 作用 |
|------|-----------|---------|
| akshare | >=1.18.0 | 金融、影视数据源 |
| beautifulsoup4 | >=4.12.0 | HTML 解析 (通用) |
| chinese-calendar | >=1.11.0 | 中国节假日判定 |
| jinja2 | >=3.1.0 | HTML 模板渲染 |
| lxml | >=6.0.0 | XML/HTML 高速解析 |
| matplotlib | >=3.10.0 | 报表绘图 |
| pandas | >=3.0.0 | 数据处理中心 |
| requests | >=2.32.0 | 网络请求 |
| feedparser | >=6.0.10 | **必需**：用于 Github Actions 抓取 RSS |
| python-dotenv | >=1.0.0 | **必需**：用于加载环境变量 |

### ❌ 移除的包
| 包名 | 原因 |
|------|------|
| **ttrss-python** | 🚀 **彻底移除**：项目已迁移至云原生，不再需要 TTRSS 后端。 |
| pytz | ❌ 无需单独安装，已集成或非必需。 |

### ⚠️ 可选安装 (Conditional)
- **playwright**: 仅在执行 `scripts/push_damai.py` 或特定爬虫时需要。
- **boto3**: 仅在执行 `scripts/backup_r2.py` 时需要。

## 升级风险提示
- **Numpy/Pandas**: 版本较新，注意旧代码中的 API 兼容性。目前 `Engine` 运行正常。
