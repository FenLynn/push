// ==========================================
// 1. 全局配置
// ==========================================
const GITHUB_OWNER = "你的GitHub用户名";
const DEFAULT_BRANCH = "main";

// ==========================================
// 2. 任务路由表 (北京时间 CST)
// ==========================================
const ROUTE_CONFIG = {
  // 每小时触发：RSS 抓取 (在脚本里特殊处理)
  "cron_hourly": [
    { repo: "push", workflow: "rss_fetch.yml" }
  ],
  // 精确时间匹配 (格式: "HH:MM", 星期可选 "1-5")
  "06:00_1-5": [{ repo: "push", workflow: "night.yml" }],
  "07:00": [{ repo: "push", workflow: "morning.yml" }],
  "07:10": [{ repo: "push", workflow: "damai.yml" }],
  "09:15": [{ repo: "push", workflow: "watchdog.yml" }],
  "10:30_1-5": [{ repo: "push", workflow: "etf.yml" }],
  "11:30_1-5": [{ repo: "push", workflow: "stock.yml" }],
  "11:32_1-5": [{ repo: "push", workflow: "etf.yml" }],
  "13:00": [{ repo: "push", workflow: "game.yml" }],
  "14:40_1-5": [{ repo: "push", workflow: "etf.yml" }],
  "15:05_1-5": [{ repo: "push", workflow: "stock.yml" }],
  "15:03_1-5": [{ repo: "push", workflow: "etf.yml" }],
  "19:00": [
    { repo: "push", workflow: "estate.yml" },
    { repo: "push", workflow: "paper.yml" }
  ],
  "20:00": [
    { repo: "push", workflow: "finance.yml" },
    { repo: "push", workflow: "fund.yml" },
    { repo: "push", workflow: "life.yml" }
  ]
};

// ==========================================
// 3. 核心执行逻辑
// ==========================================
export default {
  async scheduled(event, env, ctx) {
    const token = env.GITHUB_TOKEN;
    if (!token) {
      console.error("缺少 GITHUB_TOKEN！");
      return;
    }

    // 获取触发时的 UTC 时间，并转换为北京时间 (UTC+8)
    const now = new Date(event.scheduledTime);
    const utcHours = now.getUTCHours();
    const utcMinutes = now.getUTCMinutes();
    const utcDay = now.getUTCDay(); // 0(周日) - 6(周六)

    // 北京时间 (+8)
    let cstHours = (utcHours + 8) % 24;
    let cstDay = utcDay;
    if (utcHours + 8 >= 24) { cstDay = (cstDay + 1) % 7; } // 跨天

    const mm = utcMinutes.toString().padStart(2, '0');
    const hh = cstHours.toString().padStart(2, '0');
    const isWeekday = cstDay >= 1 && cstDay <= 5;
    
    // 当前组装的时间键，比如 "10:30"
    const timeKey = `${hh}:${mm}`;
    console.log(`当前北京时间: ${timeKey}, 星期 ${cstDay}`);

    let tasksToRun = [];

    // 1. 检查是否有每天的小时级任务 (比如00分触发RSS)
    if (mm === '00' && ROUTE_CONFIG["cron_hourly"]) {
      tasksToRun.push(...ROUTE_CONFIG["cron_hourly"]);
    }

    // 2. 检查是否有匹配当前 `${hh}:${mm}` 的任务
    if (ROUTE_CONFIG[timeKey]) {
      tasksToRun.push(...ROUTE_CONFIG[timeKey]);
    }

    // 3. 检查是否有匹配当前 `${hh}:${mm}_1-5` (工作日) 的任务
    const weekdayKey = `${timeKey}_1-5`;
    if (isWeekday && ROUTE_CONFIG[weekdayKey]) {
      tasksToRun.push(...ROUTE_CONFIG[weekdayKey]);
    }

    if (tasksToRun.length === 0) {
      console.log(`[跳过] 当前时间 ${timeKey} 没有匹配到任务。`);
      return;
    }

    console.log(`匹配成功，准备同时触发 ${tasksToRun.length} 个任务...`);

    const fetchPromises = tasksToRun.map(task => {
      const url = `https://api.github.com/repos/${GITHUB_OWNER}/${task.repo}/actions/workflows/${task.workflow}/dispatches`;
      return fetch(new Request(url, {
        method: "POST",
        headers: {
          "Accept": "application/vnd.github.v3+json",
          "Authorization": `Bearer ${token}`,
          "User-Agent": "CF-Cron",
          "X-GitHub-Api-Version": "2022-11-28"
        },
        body: JSON.stringify({ ref: task.branch || DEFAULT_BRANCH })
      })).then(res => {
        if(res.ok) console.log(`[成功] 触发: ${task.workflow}`);
        else console.error(`[失败] 触发: ${task.workflow} | HTTP ${res.status}`);
      });
    });

    await Promise.all(fetchPromises);
  }
};
