import os
import sys
from datetime import datetime, timedelta
from core.d1_client import D1Client

def check_health():
    """
    检查系统健康状况，主要查看最近 24 小时内的任务日志。
    """
    d1 = D1Client()
    if not d1.enabled:
        return "⚠️ Health Check Warning: D1 Database not accessible."

    # 核心模块列表
    core_modules = ['finance', 'paper']
    yesterday = (datetime.now() - timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
    
    warnings = []
    
    for mod in core_modules:
        sql = "SELECT status, scheduled_time FROM task_logs WHERE module = ? AND created_at > ? ORDER BY created_at DESC LIMIT 1"
        try:
            res = d1.query(sql, [mod, yesterday])
            if not res or 'data' not in res or not res['data'] or not res['data'][0]['results']:
                warnings.append(f"❌ 模块 [{mod}] 过去 24 小时无运行记录")
            else:
                last_run = res['data'][0]['results'][0]
                if last_run['status'] != 'success':
                    warnings.append(f"⚠️ 模块 [{mod}] 最近运行状态异常: {last_run['status']}")
        except Exception as e:
            warnings.append(f"❓ 检查模块 [{mod}] 时发生错误: {str(e)}")

    if not warnings:
        return "✅ 系统各项核心任务运行正常"
    
    return "\n".join(warnings)

if __name__ == "__main__":
    print(check_health())
