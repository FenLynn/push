# Dependencies Audit Report

## 检查时间
2026-02-10 22:52

## 原 requirements.txt (16个包)
```
akshare>=1.17.0
beautifulsoup4>=4.12.0
chinese-calendar>=1.9.0
feedparser>=6.0.10
jinja2>=3.1.0
lxml>=5.0.0
matplotlib>=3.7.0
numpy>=1.24.0
pandas>=2.0.0
pillow>=10.0.0
playwright>=1.40.0
pyyaml>=6.0
requests>=2.31.0
pytz>=2024.0
webdavclient3>=3.14.6
ttrss-python>=0.2.6
```

## 清理结果

### ✅ 保留的核心依赖 (12个)
| 包名 | 原版本要求 | 最新安装版本 | 使用位置 |
|------|-----------|------------|---------|
| akshare | >=1.17.0 | 1.18.22 | sources/finance, sources/life, sources/etf (金融数据) |
| beautifulsoup4 | >=4.12.0 | 4.14.3 | cloud/utils, sources/finance (HTML解析) |
| chinese-calendar | >=1.9.0 | 1.11.0 | cloud/utils (中国节假日) |
| jinja2 | >=3.1.0 | 3.1.6 | core/template, sources/paper (模板渲染) |
| lxml | >=5.0.0 | 6.0.2 | cloud/utils (XML解析) |
| matplotlib | >=3.7.0 | 3.10.8 | cloud/utils, sources/finance (绘图) |
| numpy | >=1.24.0 | 2.4.2 | cloud/utils, cloud/image (数值计算) |
| pandas | >=2.0.0 | 3.0.0 | 多处使用 (数据处理) |
| pillow | >=10.0.0 | 12.1.0 | cloud/utils (图像处理) |
| pyyaml | >=6.0 | 6.0.3 | core/env (配置文件) |
| requests | >=2.31.0 | 2.32.5 | 多处使用 (HTTP请求) |
| ttrss-python | >=0.2.6 | 0.5 | cloud/utils (RSS订阅) |

### ❌ 移除的包 (4个)
| 包名 | 原因 |
|------|------|
| feedparser | ❌ 未在代码中找到任何使用 |
| pytz | ❌ 未在代码中找到任何使用 |
| playwright | ⚠️ 仅在 scripts/crawl_*.py 使用，已标注为可选依赖 |
| webdavclient3 | ⚠️ 仅在 scripts/backup_webdav.py 使用，已标注为可选依赖 |

## 升级幅度
- **重大升级 (Major)**: pandas 2.0 → 3.0, numpy 1.24 → 2.4, matplotlib 3.7 → 3.10
- **次要升级**: 其他包均为小版本升级
- **兼容性风险**: Pandas 3.0 可能存在 API 变更，需测试

## 建议
1. 立即测试 push 核心功能 (`python main.py list`, `python main.py gen morning`)
2. 如需使用 crawler scripts，手动安装: `pip install playwright && playwright install chromium`
3. 如需 WebDAV 备份，手动安装: `pip install webdavclient3`
