# 问题诊断：Conda 创建环境速度慢

## 检查结果

### 1. 系统资源（正常）
- **内存**: 15GB 总量，12GB 可用 ✅
- **磁盘**: 94GB 总量，16GB 可用（84% 使用率，尚可）✅
- **Swap**: 5GB 可用 ✅

### 2. Conda 配置（问题所在）❌
```yaml
channels:
  - https://repo.anaconda.com/pkgs/main
  - https://repo.anaconda.com/pkgs/r
```

**问题**: 当前使用的是 **Anaconda 官方源**（美国服务器），从中国大陆访问速度极慢（之前测试延迟 190ms+）。

## 解决方案

配置 **清华大学镜像源** 或 **阿里云镜像源**，可将下载速度提升 10-100 倍。

### 方案 A: 清华源（推荐）
```bash
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/main/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/pkgs/free/
conda config --add channels https://mirrors.tuna.tsinghua.edu.cn/anaconda/cloud/conda-forge/
conda config --set show_channel_urls yes
```

### 方案 B: 阿里云源（备选）
```bash
conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/main/
conda config --add channels https://mirrors.aliyun.com/anaconda/pkgs/free/
conda config --set show_channel_urls yes
```

### 验证配置
```bash
conda config --show channels
```

### 重新创建环境
```bash
conda create -n py313 python=3.13 -y
```

预期速度提升：从 **30分钟+** -> **1-3分钟**
