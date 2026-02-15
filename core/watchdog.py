import sys
import os
sys.path.insert(0, os.getcwd())

import logging
from datetime import datetime
from core.d1_client import D1Client
from core.trading_calendar import is_a_share_trading_day
from core import Message, ContentType
from core.engine import Engine
from channels.pushplus import PushPlusChannel
import os

logger = logging.getLogger('Push.Watchdog')

# 监控配置: (模块名, 截止时间HH:MM, 是否仅交易日)
MONITOR_CONFIG = [
    ('morning', '08:45', False),
    ('finance', '08:50', False),
    ('paper', '09:00', False),
    ('stock', '12:00', True),
    ('stock', '15:45', True),
]

def run_watchdog():
    """
    实时自检心跳：检查当前时间点应该已经运行完毕的任务。
    """
    now = datetime.now()
    now_str = now.strftime("%H:%M")
    today_date = now.strftime("%Y-%m-%d")
    
    d1 = D1Client()
    if not d1.enabled:
        logger.error("Watchdog: D1 is disabled, cannot check logs.")
        return

    is_trading = is_a_share_trading_day(now)
    alerts = []

    for module, deadline, only_trading in MONITOR_CONFIG:
        if only_trading and not is_trading:
            continue
            
        if now_str > deadline:
            # 针对股市下午盘做特殊判断（检测 12:00 之后的记录）
            if module == 'stock' and deadline == '15:45':
                sql_check = "SELECT status FROM task_logs WHERE module = ? AND created_at > ? AND status = 'success' LIMIT 1"
                params = [module, f"{today_date} 12:00:00"]
            else:
                sql_check = "SELECT status FROM task_logs WHERE module = ? AND created_at LIKE ? AND status = 'success' LIMIT 1"
                params = [module, f"{today_date}%"]
                
            try:
                res = d1.query(sql_check, params)
                if not res or 'data' not in res or not res['data'] or not res['data'][0]['results']:
                    # 并未成功，尝试寻找最近的一条错误记录
                    fail_sql = "SELECT status, error_msg, created_at FROM task_logs WHERE module = ? AND created_at LIKE ? ORDER BY created_at DESC LIMIT 1"
                    fail_res = d1.query(fail_sql, [module, f"{today_date}%"])
                    
                    if fail_res and 'data' in fail_res and fail_res['data'] and fail_res['data'][0]['results']:
                        error = fail_res['data'][0]['results'][0]
                        if error['status'] != 'success':
                            alerts.append(f"❌ 模块 [{module}] 运行失败 (记录时间: {error['created_at']}): {error.get('error_msg', '未知错误')}")
                        else:
                            # 理论上不会走到这里，因为上面成功的 query 没查到
                            alerts.append(f"⚠️ 模块 [{module}] 状态异常 (预期 {deadline})")
                    else:
                        alerts.append(f"💤 模块 [{module}] 缺失运行记录 (逾期自 {deadline})")
            except Exception as e:
                logger.error(f"Watchdog error querying {module}: {e}")

    if alerts:
        send_critical_alert("\n".join(alerts))
    else:
        logger.info(f"Watchdog: All systems nominal at {now_str}.")

def send_critical_alert(content):
    """发送加急告警 (直接通过通道)"""
    print(f"[Watchdog Alert]\n{content}")
    msg = Message(
        title="🛡️ 哨兵拦截：系统运行异常",
        content=f"检测到以下任务未按预期执行，请检查云端状态：\n\n{content}",
        type=ContentType.TEXT,
        tags=['watchdog', 'alert']
    )
    
    try:
        from channels.pushplus import PushPlusChannel
        channel = PushPlusChannel()
        if channel.token:
            success = channel.send(msg)
            if success:
                print("[Watchdog] Critical alert sent successfully.")
            else:
                print("[Watchdog] PushPlus rejected the alert.")
        else:
            print("[Watchdog] PUSHPLUS_TOKEN not found, alert suppressed.")
    except Exception as e:
        print(f"[Watchdog] Error sending alert: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_watchdog()
