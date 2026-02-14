"""
Trading Calendar Utility
交易日历工具 - 判断工作日/休息日、A股/美股交易日

Features:
1. Chinese workday/holiday detection (using chinese_calendar)
2. A-share trading day detection
3. US stock trading day detection (NYSE/NASDAQ)
"""
from datetime import date, datetime, timedelta
import os
import json
import time
from typing import Optional, Dict, List
import requests
import chinese_calendar
from core.d1_client import D1Client

# US Market Holidays (approximated, update yearly)
# Source: NYSE holiday calendar
US_HOLIDAYS_2026 = [
    date(2026, 1, 1),   # New Year's Day
    date(2026, 1, 19),  # MLK Day (3rd Monday Jan)
    date(2026, 2, 16),  # Presidents Day (3rd Monday Feb)
    date(2026, 4, 3),   # Good Friday
    date(2026, 5, 25),  # Memorial Day (Last Monday May)
    date(2026, 7, 3),   # Independence Day (observed)
    date(2026, 9, 7),   # Labor Day (1st Monday Sep)
    date(2026, 11, 26), # Thanksgiving (4th Thu Nov)
    date(2026, 12, 25), # Christmas
]

# Cache for performance
_cache = {}
_holiday_data = {}
_d1_client = None

def get_d1():
    """Get or initialize D1 client"""
    global _d1_client
    if _d1_client is None:
        _d1_client = D1Client()
        if _d1_client.enabled:
            # Ensure KV table exists
            _d1_client.ensure_table('sys_kv', """
                CREATE TABLE sys_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
    return _d1_client if _d1_client and _d1_client.enabled else None

def _get_data_dir():
    """获取数据存储目录"""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    data_dir = os.path.join(base_dir, 'data')
    if not os.path.exists(data_dir):
        os.makedirs(data_dir)
    return data_dir

def sync_holidays_from_remote(year: int = None, force: bool = False) -> bool:
    """
    从远程同步节假日数据 (holiday-cn)
    """
    year = year or date.today().year
    key = f'holidays_{year}'
    
    d1 = get_d1()
    
    # 1. 检查是否需要同步 (云端持久化)
    if not force and d1:
        res = d1.query("SELECT updated_at FROM sys_kv WHERE key = ?", [key])
        if res['success'] and res['data'] and res['data'][0]['results']:
            updated_at_str = res['data'][0]['results'][0]['updated_at']
            # Simple TTL check: 7 days
            try:
                updated_at = datetime.strptime(updated_at_str, '%Y-%m-%d %H:%M:%S')
                if datetime.now() - updated_at < timedelta(days=7):
                    return True # Data is fresh enough
            except:
                pass
                
    # 2. 从 CDN 获取
    url = f"https://fastly.jsdelivr.net/gh/NateScarlet/holiday-cn@master/{year}.json"
    try:
        resp = requests.get(url, timeout=10)
        if resp.status_code == 200:
            data_json = resp.text
            
            # 存入 D1
            if d1:
                sql = "INSERT OR REPLACE INTO sys_kv (key, value, updated_at) VALUES (?, ?, datetime('now'))"
                d1.query(sql, [key, data_json])
                print(f"[Calendar] Synced holidays for {year} to D1.")
            
            # 同时存入本地缓存 (Actions 运行期间)
            cache_file = os.path.join(_get_data_dir(), f'holidays_{year}.json')
            with open(cache_file, 'w', encoding='utf-8') as f:
                f.write(data_json)
                
            return True
    except Exception as e:
        print(f"[Calendar] Remote sync failed: {e}")
    return False

def _load_holidays(year: int) -> Dict[str, bool]:
    """加载指定年份的节假日数据"""
    global _holiday_data
    if year in _holiday_data:
        return _holiday_data[year]
        
    key = f'holidays_{year}'
    d1 = get_d1()
    data_json = None
    
    # 1. 尝试从 D1 读取
    if d1:
        res = d1.query("SELECT value FROM sys_kv WHERE key = ?", [key])
        if res['success'] and res['data'] and res['data'][0]['results']:
            data_json = res['data'][0]['results'][0]['value']
            
    # 2. 如果 D1 没药，尝试本地文件 (Fallback)
    if not data_json:
        cache_file = os.path.join(_get_data_dir(), f'holidays_{year}.json')
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data_json = f.read()
                
    # 3. 如果还是没有，尝试同步
    if not data_json:
        if sync_holidays_from_remote(year):
            # 同步完再读一次 (这次从 D1 或文件)
            return _load_holidays(year)
            
    if data_json:
        try:
            data = json.loads(data_json)
            day_map = {d['date']: d['isHoliday'] for d in data.get('days', [])}
            _holiday_data[year] = day_map
            return day_map
        except:
            pass
    return {}

def is_china_workday(d: Optional[date] = None) -> bool:
    """
    判断是否为中国工作日（非周末、非法定假日，包括调休上班日）
    优先使用远程同步的最新数据，失败时回退到本地库。
    """
    d = d or date.today()
    
    # 尝试使用同步数据
    holidays = _load_holidays(d.year)
    date_str = d.strftime('%Y-%m-%d')
    if date_str in holidays:
        # isHoliday 为 True 表示放假，为 False 表示补班（即工作日）
        return not holidays[date_str]
        
    # 回退到本地库
    return chinese_calendar.is_workday(d)

def is_china_holiday(d: Optional[date] = None) -> bool:
    """
    判断是否为中国法定节假日
    """
    d = d or date.today()
    
    # 尝试使用同步数据
    holidays = _load_holidays(d.year)
    date_str = d.strftime('%Y-%m-%d')
    if date_str in holidays:
        return holidays[date_str]
        
    # 回退到本地库
    return chinese_calendar.is_holiday(d)

def get_china_holiday_name(d: Optional[date] = None) -> Optional[str]:
    """
    获取中国法定节假日名称
    优先使用自同步数据。
    """
    d = d or date.today()
    
    # 尝试使用同步数据获取名称
    year = d.year
    key = f'holidays_{year}'
    d1 = get_d1()
    data_json = None
    
    if d1:
        res = d1.query("SELECT value FROM sys_kv WHERE key = ?", [key])
        if res['success'] and res['data'] and res['data'][0]['results']:
            data_json = res['data'][0]['results'][0]['value']
            
    if not data_json:
        cache_file = os.path.join(_get_data_dir(), f'holidays_{year}.json')
        if os.path.exists(cache_file):
            with open(cache_file, 'r', encoding='utf-8') as f:
                data_json = f.read()

    if data_json:
        try:
            data = json.loads(data_json)
            date_str = d.strftime('%Y-%m-%d')
            for day in data.get('days', []):
                if day['date'] == date_str and day['isHoliday']:
                    return day['name']
        except:
            pass

    # 回退到本地库
    try:
        holiday = chinese_calendar.get_holiday_detail(d)
        if holiday[0]:  # is_holiday
            return holiday[1] if holiday[1] else None
    except:
        pass
    return None

def is_a_share_trading_day(d: Optional[date] = None) -> bool:
    """
    判断是否为A股交易日
    
    规则：
    1. 必须是工作日
    2. 非法定节假日
    3. 非周末
    
    Args:
        d: 日期，默认为今天
        
    Returns:
        bool: True=交易日, False=非交易日
    """
    d = d or date.today()
    
    # 周末不交易
    if d.weekday() >= 5:
        return False
    
    # 法定假日不交易
    if chinese_calendar.is_holiday(d):
        return False
    
    return True

def is_us_trading_day(d: Optional[date] = None) -> bool:
    """
    判断是否为美股交易日 (NYSE/NASDAQ)
    
    规则：
    1. 非周末
    2. 非美国法定假日
    
    Args:
        d: 日期，默认为今天
        
    Returns:
        bool: True=交易日, False=非交易日
    """
    d = d or date.today()
    
    # 周末不交易
    if d.weekday() >= 5:
        return False
    
    # 美国假日不交易
    if d in US_HOLIDAYS_2026:
        return False
    
    return True

def get_next_trading_day(market: str = 'CN', d: Optional[date] = None) -> date:
    """
    获取下一个交易日
    
    Args:
        market: 'CN' (A股) 或 'US' (美股)
        d: 起始日期，默认为今天
        
    Returns:
        date: 下一个交易日
    """
    d = d or date.today()
    check_func = is_a_share_trading_day if market == 'CN' else is_us_trading_day
    
    while True:
        d = d + timedelta(days=1)
        if check_func(d):
            return d

def get_trading_status() -> dict:
    """
    获取当前交易状态摘要
    
    Returns:
        dict: {
            'date': '2026-02-09',
            'weekday': 'Monday',
            'cn_workday': True,
            'cn_holiday': None,
            'a_share_trading': True,
            'us_trading': True,
            'next_cn_trading': '2026-02-10',
            'next_us_trading': '2026-02-10',
        }
    """
    today = date.today()
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
    
    return {
        'date': today.isoformat(),
        'weekday': weekdays[today.weekday()],
        'weekday_cn': ['周一', '周二', '周三', '周四', '周五', '周六', '周日'][today.weekday()],
        'cn_workday': is_china_workday(today),
        'cn_holiday': get_china_holiday_name(today),
        'a_share_trading': is_a_share_trading_day(today),
        'us_trading': is_us_trading_day(today),
        'next_cn_trading': get_next_trading_day('CN', today).isoformat() if not is_a_share_trading_day(today) else None,
        'next_us_trading': get_next_trading_day('US', today).isoformat() if not is_us_trading_day(today) else None,
    }

def should_push_module(module_name: str) -> bool:
    """
    根据交易日状态判断是否应该推送某模块
    
    Args:
        module_name: 模块名称
        
    Returns:
        bool: True=应该推送, False=不应推送
    """
    today = date.today()
    
    # 模块推送规则
    rules = {
        'morning': lambda: True,  # 每天推送
        'finance': lambda: is_china_workday(today),  # 中国工作日 (包含补班)
        'stock': lambda: is_china_workday(today),
        'etf': lambda: is_china_workday(today),
        'fund': lambda: is_china_workday(today),
        'night': lambda: is_us_trading_day(today),  # 美股交易日
        'paper': lambda: True,  # 每天推送
        'game': lambda: True,
        'life': lambda: True,
        'estate': lambda: is_china_workday(today),  # 中国工作日
        'damai': lambda: True,
    }
    
    check = rules.get(module_name)
    if check:
        return check()
    return True  # 默认推送

# CLI Test
if __name__ == "__main__":
    print("=" * 50)
    print("Trading Calendar Utility Test")
    print("=" * 50)
    
    status = get_trading_status()
    for k, v in status.items():
        print(f"  {k}: {v}")
    
    print("\n--- Module Push Status ---")
    modules = ['morning', 'finance', 'stock', 'night', 'paper', 'estate']
    for m in modules:
        print(f"  {m}: {'✅ Push' if should_push_module(m) else '⏸️ Skip'}")
