# Push 项目使用指南

## 🎯 推送到不同组别

PushPlus 支持 **topic（主题组）**功能，可以将消息推送到不同的群组。

### 主题组说明

| Topic | 说明 | 用途 |
|-------|------|------|
| `me` | 默认（推送给自己） | 个人接收 |
| `stock` | 股票组 | 投资理财相关 |
| `family` | 家庭组 | 家人共享 |
| `baobao` | 宝宝组 | 孩子相关信息 |

### 推送命令

```bash
# 1. 推送给自己（默认 topic=me）
python main.py run morning

# 2. 推送到股票组
python main.py run finance --topic stock

# 3. 推送到家庭组
python main.py run estate --topic family

# 4. 推送到宝宝组
python main.py run game --topic baobao

# 5. 一次推送多个模块到同一组
python main.py run @stock --topic stock
# 相当于: finance + stock + etf + fund → 推送到 stock 组
```

---

## 📱 如何在 PushPlus 创建主题组

### 步骤 1: 登录 PushPlus
访问 [https://pushplus.plus/](https://pushplus.plus/) 并登录

### 步骤 2: 创建主题
1. 进入"一对多推送" → "群组管理"
2. 点击"新建群组"
3. 设置群组名称，例如：
   - `stock` - 股票投资组
   - `family` - 家庭组
   - `baobao` - 宝宝成长组

### 步骤 3: 获取群组二维码
- 每个群组会生成一个二维码
- 家人/朋友扫码即可加入该群组

### 步骤 4: 推送到群组
```bash
# 推送财经信息到 stock 组
python main.py run finance --topic stock

# 推送房产信息到 family 组
python main.py run estate --topic family
```

---

## 🔧 常用推送方案

### 方案 1: 个人早报（推送给自己）
```bash
python main.py run morning paper --topic me
```

### 方案 2: 股票组推送（傍晚 18:00）
```bash
python main.py run @stock --topic stock
# 包含: finance, stock, etf, fund
```

### 方案 3: 家庭组推送（周一早上）
```bash
python main.py run morning estate --topic family
```

### 方案 4: 宝宝组推送（中午 12:00）
```bash
python main.py run @baobao --topic baobao
# 包含: morning, game, life
```

---

## ⚙️ Cron 定时推送

编辑 `config/crontab.txt`，设置不同时间推送到不同组：

```cron
# 每天 08:00 推送早报给自己
0 8 * * * python /app/main.py run morning paper --topic me

# 工作日 18:00 推送股票信息到 stock 组
0 18 * * 1-5 python /app/main.py run @stock --topic stock

# 周一 09:00 推送房产信息到 family 组
0 9 * * 1 python /app/main.py run estate --topic family

# 每天 12:00 推送游戏赛程到 baobao 组
0 12 * * * python /app/main.py run game --topic baobao
```

---

## ✅ 验证推送

运行单个模块测试：
```bash
# 测试推送论文到自己
python main.py run paper --topic me

# 测试推送财经到 stock 组
python main.py run finance --topic stock
```

检查微信是否收到消息！🎉
