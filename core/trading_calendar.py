"""
Trading Calendar Utility
交易日历工具 - 判断工作日/休息日、A股/美股交易日

Features:
1. Chinese workday/holiday detection (using chinese_calendar)
2. A-share trading day detection
3. US stock trading day detection (NYSE/NASDAQ)
"""
from datetime import date, datetime, timedelta
from typing import Optional
import chinese_calendar

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

def is_china_workday(d: Optional[date] = None) -> bool:
    """
    判断是否为中国工作日（非周末、非法定假日，包括调休上班日）
    
    Args:
        d: 日期，默认为今天
        
    Returns:
        bool: True=工作日, False=休息日
    """
    d = d or date.today()
    return chinese_calendar.is_workday(d)

def is_china_holiday(d: Optional[date] = None) -> bool:
    """
    判断是否为中国法定节假日
    
    Args:
        d: 日期，默认为今天
        
    Returns:
        bool: True=法定假日, False=非法定假日
    """
    d = d or date.today()
    return chinese_calendar.is_holiday(d)

def get_china_holiday_name(d: Optional[date] = None) -> Optional[str]:
    """
    获取中国法定节假日名称
    
    Args:
        d: 日期，默认为今天
        
    Returns:
        str or None: 节假日名称，如 "春节"、"国庆节"
    """
    d = d or date.today()
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
        'finance': lambda: is_a_share_trading_day(today),  # A股交易日
        'stock': lambda: is_a_share_trading_day(today),
        'etf': lambda: is_a_share_trading_day(today),
        'fund': lambda: is_a_share_trading_day(today),
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
