from .config import *
from .utils.lib import *

def get_time_ymdhms_str():
    current_time = datetime.now().strftime("%Y%m%d_%H%M%S")
    return current_time

def get_time_ym_str():
    current_time = datetime.now().strftime("%Y%m")
    return current_time

def get_time_ymd_str():
    current_time = datetime.now().strftime("%Y%m%d")
    return current_time


def get_str_date(s):
    pattern_date = re.compile(r'\d{4}[-/]?\d{2}[-/]?\d{2}')
    match=pattern_date.findall(s)[0]
    return match
    
def get_str_time(s):
    pattern_time = re.compile(r'\d{1,2}:\d{1,2}')
    match=pattern_time.findall(s)[0]
    return match

def is_work_day():
    april_last = date(2023, 4, 5)   # datetime.date
    print(is_workday(april_last))     # True
    print(is_holiday(april_last))     # False
    print(april_last.weekday())       # 5-星期六

# 当前日期N天前的证券交易日
def get_trade_day(n=0):
    dt = date.today()
    #dt = date(2023,4,4)
    #trade_day = '20201026'
    if n < 0:
        t = -n
    else:
        t = n
    for i in range(100):
        if n<0:
            delta_day = timedelta(days=-i)
        else:
            delta_day = timedelta(days=i)
        trade_day = dt-delta_day
        if is_workday(trade_day) and trade_day.weekday()<5:       # 工作日并且不是周末
            if t ==0:
                break
            t = t -1
    #print(trade_day.strftime('%Y-%m-%d'))
    return trade_day.strftime('%Y-%m-%d')


def get_today_trade_status():
    dt = date.today()
    current_trade_day=get_trade_day(0)
    if current_trade_day == dt.strftime('%Y-%m-%d'):
        return True
    else:
        return False
    
def get_today_status():
    def get_weekdays():
        week_list = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
        local_time = time.localtime(time.time())   # 获取当前时间的时间元组        
        week_index = local_time.tm_wday  # 获取时间元组内的tm_wday值
        week = week_list[week_index]
        return week 
    
    
    last_trade_day=get_trade_day(1)
    current_trade_day=get_trade_day(0)
    dt = date.today()
    _workday=is_workday(dt)
    _holiday=is_holiday(dt)
    _OnHoliday, _HolidayName = get_holiday_detail(dt)

    
    _status=''
    _trade_status=False 
    
    
    if _workday:
        if get_weekdays() in ["星期一", "星期二", "星期三", "星期四", "星期五"]:
            _status='工作日正常`上班`'
        elif get_weekdays() in ["星期六", "星期日"]:
            _status='周末调休`上班`'
        else:
            _status='异常状态'
    elif _holiday:
        if  _HolidayName:
            _status = '节假日`休息`:{0}'.format(_HolidayName)
        elif get_weekdays() in ["星期六", "星期日"]:
            _status = '周末正常`休息`'
        else:
            _status = '工作日调休`休息`'
    
    if current_trade_day == dt.strftime('%Y-%m-%d'):
        _status+=', A股`开盘`'
        _trade_status=True 
    else:
        _status+=', A股`不开盘`'
        _trade_status=False
    return _status

def timer_decorator(func):
    def wrapper(*args, **kwargs):
        start = time.perf_counter() 
        result = func(*args, **kwargs)
        end = time.perf_counter() 
        print(f"{func.__name__} 耗时：{end - start:.4f}秒")
        return result 
    return wrapper

def is_today_trade():
    import akshare as ak
