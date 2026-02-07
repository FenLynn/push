# Index Valuation Daily (指数估值日报)

> **Current Version**: V2.2 (Final)
> **Last Updated**: 2026-02-05

## 1. 模块简介 (Overview)
本模块 (`sources/fund`) 负责抓取各大宽基与行业指数的估值数据（PE/PB/股息率/ROE），生成一份媲美券商研报的 HTML 日报，并通过 PushPlus 推送。
核心目标是在 **极度受限的 PushPlus 单条消息体积 (15KB)** 内，提供 **信息密度最高、视觉体验最佳** 的估值日报。

## 2. 核心特性 (Features)

### 2.1 视觉与交互 (UI/UX)
- **红白渐变表头**: 采用 CSS3 `linear-gradient` + `box-shadow` 打造悬浮卡片质感，搭配 "📈" 动态图标。
- **三段式布局**: 根据估值状态自动分组：
  - 🟢 **低估机会**: 重点展示，前三名自动加冕 "👑" 皇冠。
  - 🟠 **正常估值**: 紧凑展示。
  - 🔴 **高估风险**: 警示展示。
- **智能高亮 (Smart Highlights)**:
  - **黄金指数 (Golden ROE)**: 若 ROE > 15%，指数名称显示为 **深金色 (Bold Gold)**，提示长期投资价值。
  - **高股息 (High Yield)**: 若股息率 > 4%，数值显示为 **红色 (Hot Red)**，提示现金流价值。
- **一致性体验**: 底部图例、Tips 提示均统一为 **14px** 字号，左对齐排版。

### 2.2 极限体积优化 (Size Optimization)
为了解决 PushPlus >15KB 会自动分页 (变成 "1/2", "2/2") 的痛点，本模块实施了 **"单页承诺"** 计划：
1.  **HTML Minification**: 移除所有换行符、空格和 CSS 注释。
2.  **变量名混淆 (Obfuscation)**:
    -   Python 传输到 Template 的变量名被强制缩短（如 `funds_low` -> `f_l`），节省约 500 字节。
3.  **属性精简**:
    -   移除了所有 `target="_blank"`（移动端默认新窗口），节省约 1KB。
4.  **Inline Style 兼容**:
    -   针对 "黄金 ROE" 等关键样式，使用 `style="..."` 内联写法，确保在不支持 CSS Class 的邮件客户端（如 Gmail/Outlook）中也能正确显示。

## 3. 技术架构 (Architecture)

- **数据源**: 蛋卷基金 API (`danjuanapp.com`)
- **模板引擎**: Jinja2 (`templates/fund.html`)
- **数据持久化**: `CoreDB` 表 `fund_valuation`
- **运行命令**:
    ```bash
    python main.py run fund
    ```

## 4. 版本演进 (Changelog)

| 版本 | 日期 | 核心变更 |
| :--- | :--- | :--- |
| **V2.2** | 2026-02-05 | **定型版**。图例字号统一 14px，正式更名为 "指数估值日报"。 |
| **V2.1** | 2026-02-05 | 修正语义，将 "Fund" 概念纠正为 "Index"。 |
| **V2.0** | 2026-02-05 | **视觉里程碑**。引入渐变表头、底部 Tips，实施变量名混淆 (`f_l`) 确保单页。 |
| **V1.9** | 2026-02-05 | 修复黄金 ROE 在邮件中不显示的问题 (转为 Inline Style)。 |
| **V1.0** | 2026-02-04 | 初始版本，实现基础的三段式分组和数据抓取。 |

## 5. 开发注意
- **不要轻易修改变量名**: `source.py` 中的 `f_l`, `f_m`, `f_h` 与 `fund.html` 严格对应，修改回长变量名会导致消息体积超标分页。
- **CSS 兼容性**: 修改样式时优先使用简单 CSS 属性，避免复杂的布局（如 Grid），以兼容老旧邮件客户端。
