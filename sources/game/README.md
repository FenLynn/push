# 🎮 Game Module (电竞/游戏赛程)

此模块用于抓取并生成各类电子竞技赛事（LOL, KPL, DOTA2 等）的近期赛程表，支持每日推送。

## ✨ 核心功能 (Features)

*   **多源覆盖**: 支持英雄联盟 (LPL, LCK, LEC...), 王者荣耀 (KPL), DOTA2 等主流电竞赛事。
*   **智能排版**:
    *   **紧凑布局**: 专为手机屏幕优化的 CSS 布局，信息密度高的同事保持良好的阅读体验。
    *   **暗色模式**: 完美支持 iOS/Android 系统深色模式 (Dark Mode)，夜间阅读不刺眼。
    *   **智能截断**: 内置动态排版引擎，自动计算消息体积。若超过单条推送限制 (12KB)，自动按天裁切，确保消息**永远单页直达**，绝不分页。
*   **视觉增强**:
    *   **Hero Match**: 每日通过算法（决赛 > 淘汰赛 > T1/GEN等流量队）自动甄选一场"焦点战"，以 Cyberpunk 风格横幅置顶展示。
    *   **动态高亮**: 自动高亮关键战队 (如 T1, GEN, BLG) 的比赛。
    *   **赛事角标**: 针对不同游戏类型 (LOL/KPL/DOTA) 显示专属配色的 Pills 标签。

## 🛠️ 这里如何工作 (How it works)

1.  **数据获取**: 
    *   通过 `cloud.get_game_schedule()` 从外部数据源 (如直播8) 获取原始数据。
    *   数据清洗：去除"互动直播"等无效文本，统一时间格式。
2.  **数据处理 (`GameSource`)**:
    *   `_pick_hero_match`: 评分系统选出今日最佳比赛。
    *   `_get_formatted_data`: 格式化数据，注入 CSS 类名和高亮标记。
3.  **页面生成 Template**:
    *   使用 `templates/game.html` (Jinja2) 渲染 HTML。
    *   **Minification**: 渲染后自动执行 HTML 代码压缩（去注释、去空格），极致缩减体积。

## ⚙️ 配置 (Configuration)

文件位置: `sources/game/source.py`

*   **默认关注赛事**: 修改 `DEFAULT_GAMES` 列表。
*   **高亮战队**: 修改 `HIGHLIGHTED_TEAMS` 列表 (如 `['T1', 'GEN', 'BLG']`)。
*   **体积限制**: `MAX_MESSAGE_SIZE` 默认设为 12000 字节 (PushPlus 单页安全线)。

## 🚀 使用方法 (Usage)

**单独运行测试**:
```bash
python main.py run game
```

**快速重推 (不重新抓取)**:
```bash
python main.py send game
```
