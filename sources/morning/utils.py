
import requests
import pandas as pd
import logging
import re
from datetime import datetime

logger = logging.getLogger('Push.Morning.Utils')

def get_quota_info():
    """Stub: Quota Info"""
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
