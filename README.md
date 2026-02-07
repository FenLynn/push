# Push - 多功能信息推送系统

这是一个基于 Python 的多功能信息推送系统，遵循 IFTTT (If This Then That) 模式，旨在将分散的信息（天气、股市、论文、赛程、影视等）通过统一的接口推送到微信等通道。

## 🌟 核心特性

- **IFTTT 架构**: 数据源 (Source) 与推送通道 (Channel) 完全解耦。
- **模块化设计**: 轻松添加新的信息源或推送方式。
- **统一入口**: 通过 `main.py` 即可管理和运行所有任务。
- **环境自适应**: 自动检测运行环境并加载相应配置（本地/云服务器）。
- **健壮性**: 内置内容自动分割（处理长度限制）、日志系统和配置验证。

## 📁 目录结构

- `core/`: 核心引擎、模板处理、分割器和日志。
- `sources/`: 各类信息源实现（早报、证券、论文、影视等）。
- `channels/`: 推送通道实现（目前支持 PushPlus）。
- `templates/`: HTML 渲染模板。
- `cloud/`: 核心底层工具库。
- `main.py`: 统一命令行入口。

## 🚀 快速开始

### 1. 环境准备

建议使用 Python 3.9 环境。

```bash
conda create -n py39 python=3.9
conda activate py39
pip install -r requirements.txt
```

### 2. 配置敏感信息

通过环境变量设置关键 Token 和密码：

```bash
export PUSHPLUS_TOKEN="你的PushPlus令牌"
export TTRSS_PASSWORD="RSS服务密码"
```

### 3. 使用命令行

```bash
# 列出所有可用模块
python main.py list

# 运行特定模块
python main.py run morning stock

# 运行所有模块
python main.py run all
```

## ⏰ 自动化部署

参考 `crontab.txt` 配置定时任务。确保在 crontab 中正确设置 `PUSHPLUS_TOKEN` 等环境变量。

## 🛠️ 扩展开发

1. 在 `sources/` 下继承 `BaseSource` 创建新的类。
2. 在 `main.py` 的 `MODULES` 字典中注册该类。
3. 运行测试并部署。

## 📄 开源协议

MIT License
