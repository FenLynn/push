"""
Daily Task Scheduler & Execution Tracker
每日任务调度器与执行跟踪器

功能：
1. 根据交易日/工作日状态计划当天应运行的模块
2. 记录模块执行状态（成功/失败/跳过）
3. 提供每日摘要
"""
import json
# Database path
import json
import sqlite3
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any
from enum import Enum

# Import trading calendar
from core.trading_calendar import (
    is_china_workday, 
    is_a_share_trading_day, 
    is_us_trading_day,
    get_china_holiday_name
)

# Database path
from core.db import db as core_db


class TaskStatus(Enum):
    PENDING = "pending"       # 待执行
    RUNNING = "running"       # 执行中
    SUCCESS = "success"       # 成功
    FAILED = "failed"         # 失败
    SKIPPED = "skipped"       # 跳过（条件不满足）
    
# 模块调度规则配置
MODULE_SCHEDULE = {
    'morning': {
        'desc': '早报 (天气/金融/英语)',
        'time': '08:00',
        'condition': lambda: True,  # 每天运行
        'group': 'daily'
    },
    'finance': {
        'desc': '财经日报 (宏观/市场)',
        'time': '18:00',
        'condition': lambda: is_a_share_trading_day(),  # A股交易日
        'group': 'stock'
    },
    'paper': {
        'desc': '论文 (TTR RSS)',
        'time': '08:00',
        'condition': lambda: True,  # 每天运行
        'group': 'daily'
    },
    'stock': {
        'desc': '股票行情',
        'time': '18:00',
        'condition': lambda: is_a_share_trading_day(),
        'group': 'stock'
    },
    'etf': {
        'desc': 'ETF监控',
        'time': '18:00',
        'condition': lambda: is_a_share_trading_day(),
        'group': 'stock'
    },
    'fund': {
        'desc': '基金估值',
        'time': '18:00',
        'condition': lambda: is_a_share_trading_day(),
        'group': 'stock'
    },
    'night': {
        'desc': '美股夜盘',
        'time': '07:00',  # 次日早晨推送前夜数据
        'condition': lambda: is_us_trading_day(date.today() - timedelta(days=1)),  # 前一日美股交易
        'group': 'us'
    },
    'game': {
        'desc': '游戏赛程',
        'time': '12:00',
        'condition': lambda: True,
        'group': 'daily'
    },
    'life': {
        'desc': '影视数据',
        'time': '12:00',
        'condition': lambda: True,
        'group': 'daily'
    },
    'estate': {
        'desc': '成都房产',
        'time': '19:00',
        'condition': lambda: True,  # 每天运行 (之前是周一)
        'group': 'daily'
    },
    'damai': {
        'desc': '大麦演出',
        'time': '12:00',
        'condition': lambda: True,
        'group': 'daily'
    },
    'archive_env': {
        'desc': '环境存档',
        'time': '08:00',
        'condition': lambda: True,
        'group': 'daily'
    },
    'archive_ops': {
        'desc': '资产存档',
        'time': '09:00',
        'condition': lambda: True,
        'group': 'daily'
    },
    'archive_tech': {
        'desc': '科技存档',
        'time': '10:00',
        'condition': lambda: True,
        'group': 'daily'
    },
    'archive_vps': {
        'desc': '主机存档',
        'time': '23:59',
        'condition': lambda: True,
        'group': 'daily'
    },
    'report_weekly': {
        'desc': '周报总结',
        'time': '22:00',
        'condition': lambda: datetime.now().weekday() == 6, # Sunday
        'group': 'weekly'
    },
}

# Schema
SCHEMA = """
CREATE TABLE IF NOT EXISTS task_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT NOT NULL,
    module TEXT NOT NULL,
    scheduled_time TEXT,
    should_run INTEGER DEFAULT 1,
    status TEXT DEFAULT 'pending',
    start_time TEXT,
    end_time TEXT,
    error_message TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(date, module)
);

CREATE INDEX IF NOT EXISTS idx_date ON task_log(date);
CREATE INDEX IF NOT EXISTS idx_status ON task_log(status);
"""

class TaskScheduler:
    """每日任务调度器"""
    
    def __init__(self):
        self._init_db()
    
    def _init_db(self):
        """初始化数据库"""
        with core_db.get_connection() as conn:
            conn.executescript(SCHEMA)
            conn.commit()

    
    def plan_day(self, target_date: date = None) -> Dict[str, Dict]:
        """
        计划一天的任务
        
        Args:
            target_date: 目标日期，默认今天
            
        Returns:
            dict: {模块名: {should_run, desc, time, condition_met}}
        """
        target_date = target_date or date.today()
        date_str = target_date.isoformat()
        
        plan = {}
        
        for module, config in MODULE_SCHEDULE.items():
            # 检查条件
            try:
                should_run = config['condition']()
            except Exception as e:
                should_run = False
            
            plan[module] = {
                'should_run': should_run,
                'desc': config['desc'],
                'time': config['time'],
                'group': config['group'],
            }
            
            # 写入数据库
            self._record_plan(date_str, module, config['time'], should_run)
        
        return plan
    
    def _record_plan(self, date_str: str, module: str, scheduled_time: str, should_run: bool):
        """记录计划到数据库"""
        sql = """
        INSERT OR REPLACE INTO task_log 
        (date, module, scheduled_time, should_run, status)
        VALUES (?, ?, ?, ?, 'pending')
        """
        with core_db.get_connection() as conn:
            conn.execute(sql, (date_str, module, scheduled_time, int(should_run)))
            conn.commit()
    
    def record_start(self, module: str, target_date: date = None):
        """记录任务开始"""
        target_date = target_date or date.today()
        sql = """
        UPDATE task_log 
        SET status = 'running', start_time = ?
        WHERE date = ? AND module = ?
        """
        with core_db.get_connection() as conn:
            conn.execute(sql, (datetime.now().isoformat(), target_date.isoformat(), module))
            conn.commit()
    
    def record_success(self, module: str, target_date: date = None):
        """记录任务成功"""
        target_date = target_date or date.today()
        sql = """
        UPDATE task_log 
        SET status = 'success', end_time = ?
        WHERE date = ? AND module = ?
        """
        with core_db.get_connection() as conn:
            conn.execute(sql, (datetime.now().isoformat(), target_date.isoformat(), module))
            conn.commit()
    
    def record_failure(self, module: str, error: str = None, target_date: date = None):
        """记录任务失败"""
        target_date = target_date or date.today()
        sql = """
        UPDATE task_log 
        SET status = 'failed', end_time = ?, error_message = ?
        WHERE date = ? AND module = ?
        """
        with core_db.get_connection() as conn:
            conn.execute(sql, (datetime.now().isoformat(), error, target_date.isoformat(), module))
            conn.commit()
    
    def record_skip(self, module: str, reason: str = None, target_date: date = None):
        """记录任务跳过"""
        target_date = target_date or date.today()
        sql = """
        UPDATE task_log 
        SET status = 'skipped', error_message = ?
        WHERE date = ? AND module = ?
        """
        with core_db.get_connection() as conn:
            conn.execute(sql, (reason or "条件不满足", target_date.isoformat(), module))
            conn.commit()
    
    def get_day_status(self, target_date: date = None) -> List[Dict]:
        """获取一天的任务状态"""
        target_date = target_date or date.today()
        sql = "SELECT * FROM task_log WHERE date = ? ORDER BY scheduled_time"
        
        with core_db.get_connection() as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.execute(sql, (target_date.isoformat(),))
            return [dict(row) for row in cursor.fetchall()]
    
    def get_daily_summary(self, target_date: date = None) -> Dict:
        """
        获取每日摘要
        
        Returns:
            {
                'date': '2026-02-09',
                'is_workday': True,
                'is_cn_trading': True,
                'is_us_trading': True,
                'holiday': None,
                'total_planned': 8,
                'success': 6,
                'failed': 1,
                'pending': 1,
                'skipped': 0,
                'failed_modules': [{'module': 'finance', 'error': '...'}],
                'pending_modules': ['estate'],
            }
        """
        target_date = target_date or date.today()
        tasks = self.get_day_status(target_date)
        
        # 统计
        should_run_tasks = [t for t in tasks if t['should_run']]
        success = [t for t in should_run_tasks if t['status'] == 'success']
        failed = [t for t in should_run_tasks if t['status'] == 'failed']
        pending = [t for t in should_run_tasks if t['status'] == 'pending']
        skipped = [t for t in tasks if t['status'] == 'skipped']
        
        return {
            'date': target_date.isoformat(),
            'weekday': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][target_date.weekday()],
            'is_workday': is_china_workday(target_date),
            'is_cn_trading': is_a_share_trading_day(target_date),
            'is_us_trading': is_us_trading_day(target_date),
            'holiday': get_china_holiday_name(target_date),
            'total_planned': len(should_run_tasks),
            'success_count': len(success),
            'failed_count': len(failed),
            'pending_count': len(pending),
            'skipped_count': len(skipped),
            'success_modules': [t['module'] for t in success],
            'failed_modules': [{'module': t['module'], 'error': t.get('error_message')} for t in failed],
            'pending_modules': [t['module'] for t in pending],
            'all_tasks': tasks,
        }
    
    def should_run_today(self, module: str) -> bool:
        """检查模块今天是否应该运行"""
        config = MODULE_SCHEDULE.get(module)
        if not config:
            return True  # 未配置的模块默认运行
        
        try:
            return config['condition']()
        except:
            return True

# 全局实例
_scheduler = None

def get_scheduler() -> TaskScheduler:
    """获取全局调度器实例"""
    global _scheduler
    if _scheduler is None:
        _scheduler = TaskScheduler()
    return _scheduler

# CLI Test
if __name__ == "__main__":
    print("=" * 60)
    print("Task Scheduler Test")
    print("=" * 60)
    
    scheduler = TaskScheduler()
    
    # 计划今天的任务
    print("\n--- Today's Plan ---")
    plan = scheduler.plan_day()
    for module, info in plan.items():
        status = "✅ 应运行" if info['should_run'] else "⏸️ 跳过"
        print(f"  {info['time']} {module:12s} {status} - {info['desc']}")
    
    # 模拟执行
    print("\n--- Simulating Execution ---")
    scheduler.record_start('morning')
    scheduler.record_success('morning')
    scheduler.record_start('finance')
    scheduler.record_failure('finance', 'API 超时')
    
    # 获取摘要
    print("\n--- Daily Summary ---")
    summary = scheduler.get_daily_summary()
    print(f"日期: {summary['date']} ({summary['weekday']})")
    print(f"工作日: {summary['is_workday']}, A股交易: {summary['is_cn_trading']}, 美股交易: {summary['is_us_trading']}")
    print(f"计划任务: {summary['total_planned']}, 成功: {summary['success_count']}, 失败: {summary['failed_count']}, 待执行: {summary['pending_count']}")
    
    if summary['failed_modules']:
        print("\n❌ 失败模块:")
        for f in summary['failed_modules']:
            print(f"  - {f['module']}: {f['error']}")
