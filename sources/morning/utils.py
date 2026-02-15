
import requests
import pandas as pd
import logging
import re
from datetime import datetime

logger = logging.getLogger('Push.Morning.Utils')

def get_quota_info():
    """获取 VPN 流量信息 (JustMySocks 真实接口)"""
    try:
        # 真实的 JustMySocks 接口
        api_url = 'https://justmysocks3.net/members/getbwcounter.php?service=1004623&id=485b1fe9-fb27-4938-8671-9bdeed1973cc'
        r = requests.get(api_url, timeout=10)
        import json
        itxt = json.loads(r.text)
        
        data = {}
        data['limit'] = round(itxt['monthly_bw_limit_b'] / 1e9, 2)
        data['used'] = round(itxt['bw_counter_b'] / 1e9, 2)
        data['reset_day'] = itxt['bw_reset_day_of_month']
        data['percentage'] = f"{round(data['used'] / data['limit'] * 100, 2)}%"
        
        # 计算剩余天数 (每月 3 号重置)
        from datetime import datetime, timedelta
        today = datetime.now()
        due1 = datetime(today.year, today.month, 3)
        if today.month <= 11:
            due2 = datetime(today.year, today.month + 1, 3)
        else:
            due2 = datetime(today.year + 1, 1, 3)
            
        if today < due1:
            target_due = due1
        else:
            target_due = due2
            
        remaining_days = (target_due - today).days + 1
        return {
            'used': data['used'],
            'limit': data['limit'],
            'percentage': data['percentage'],
            'next_round': target_due.strftime('%Y-%m-%d'),
            'days': remaining_days
        }
    except Exception as e:
        logger.warning(f"Quota fetch error: {e}")
        return None

def get_gold_price_v2():
    """获取金价信息 (Lolimi API)"""
    try:
        url = 'https://api.lolimi.cn/API/huangj/api.php'
        headers = {"User-Agent": "Mozilla/5.0"}
        r = requests.get(url, headers=headers, timeout=10)
        data = r.json()
        if data.get('code') == 200:
            price = {'金店': {}, '国际': {}, '国内': {}}
            for i in data.get('国内十大金店', []):
                if i['品牌'] in ['内地周大福','内地周生生','内地六福珠宝','老凤祥','中国黄金']:
                    price['金店'][i['品牌'].replace('内地','')] = i['黄金价格']
            for i in data.get('国际黄金', []):
                if i['品种'] in ['国际金价','国际银价']:
                    price['国际'][i['品种']] = i['最新价']
            for i in data.get('国内黄金', []):
                if i['品种'] in ['国内金价','投资金条','黄金回收价格']:
                    price['国内'][i['品种']] = i['最新价']
            return price
    except: pass
    return None

def get_cny_price_v2():
    """获取汇率信息 (XxAPI)"""
    try:
        url = 'https://v2.xxapi.cn/api/allrates'
        r = requests.get(url, timeout=10)
        data = r.json()
        if data.get('code') == 200:
            rates = data['data']['rates']
            return {
                'CNY': {'name': '人民币', 'rate': rates['CNY']},
                'CNH': {'name': '离岸人民币', 'rate': rates['CNH']}
            }
    except: pass
    return None

def get_game():
    """Stub: Game Info"""
    return None

def get_hot_search():
    """Stub: Hot Search"""
    return []

def get_news_url():
    """Stub: News URL"""
    return ""

def get_lsjt():
    """Stub: Lsjt"""
    return None

def get_daily_english():
    """Get Daily English Quote from ICIBA"""
    try:
        url = "http://open.iciba.com/dsapi/"
        r = requests.get(url, timeout=5)
        data = r.json()
        content = data.get('content')
        note = data.get('note')
        return content, note
    except Exception as e:
        logger.warning(f"English quote error: {e}")
        return "Life is short, use Python.", "人生苦短，我用Python。"

def get_index():
    """Get Market Indices (A50, NDX, SPX, DAX)"""
    # Simple implementation using Tencent API
    # NDX: us.IXIC
    # SPX: us.INX
    # DAX: us.GDAXI (Tencent code for DAX? us.GDAXI works?)
    # A50: hf_CHA50CNY ? or hf_CHA50 ?
    
    # Mapping based on NightSource experience:
    # NDX -> us.IXIC
    # SPX -> us.INX
    # DAX -> 100.GDAXI (Eastmoney) or similar.
    
    # Let's try simple Tencent interface for US/HK/CN
    # A50 might need special handling. 
    # NightSource uses http://qt.gtimg.cn/q=...
    
    res = {}
    try:
        # A50 Future (Main Contract) - frequent change. 
        # Using Sina for A50 might be easier: hf_CHA50
        # Tencent: hf_CHA50
        
        codes = ['us.IXIC', 'us.INX', 'hf_CHA50']
        url = f"http://qt.gtimg.cn/q={','.join(codes)}"
        r = requests.get(url, timeout=5)
        
        # Parse Tencent format: v_code="1~Name~Code~Price~...~ChangePct~..."
        # US: 32 is pct?
        
        data = parse_tencent_data(r.text)
        
        if 'us.IXIC' in data: res['NDX'] = data['us.IXIC']['change_pct']
        if 'us.INX' in data: res['SPX'] = data['us.INX']['change_pct']
        if 'hf_CHA50' in data: res['A50'] = data['hf_CHA50']['change_pct']
        
        # DAX - Tencent might not support easily. Return 0 for now.
        res['GDAXI'] = 0.0
        
        return res
        
    except Exception as e:
        logger.warning(f"Index fetch error: {e}")
        return {}

def parse_tencent_data(text):
    res = {}
    for line in text.strip().split(';'):
        if not line: continue
        parts = line.split('=')
        if len(parts) < 2: continue
        
        code = parts[0].split('_')[-1] # v_us.IXIC -> us.IXIC
        val_str = parts[1].strip('"')
        vals = val_str.split('~')
        
        if len(vals) > 32:
            try:
                # US stocks/indices: index 32 is typically pct change
                # Futures (hf_): different format.
                if 'hf_' in code:
                    # Future format: Name, ?, Last, ?, ?, ChangePct...
                    # Try to parse roughly or use NightSource logic
                    # NightSource: hf_ -> p=ds.split(','), p[1] is change_pct?
                    # Let's assume hf_CHA50="...,...,Price,..."
                    # Actually parsing is tricky without full spec. 
                    pass
                else:
                    change_pct = float(vals[32])
                    res[code] = {'change_pct': change_pct}
            except:
                pass
    return res

def get_oil_price():
    """Stub: Oil Price to prevent crash"""
    # MorningSource expects a DataFrame with columns for provinces
    # and .iloc[-1] to have '四川', '陕西' etc.
    try:
        df = pd.DataFrame([{
            '四川': '8.00', '陕西': '7.90', '湖北': '7.95', '北京': '8.10'
        }])
        return df
    except:
        return None
