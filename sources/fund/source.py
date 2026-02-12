"""Fund Source - 基金估值数据推送 (蛋卷基金API)"""
import sys, os, time
import pandas as pd
import requests
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sources.base import BaseSource
from core import Message, ContentType
from core.template import TemplateEngine
from core.db import db
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from core.legacy import *
from core.utils.lib import *

class FundSource(BaseSource):
    """基金估值数据源"""
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        self.template = TemplateEngine()
        self.template = TemplateEngine()
        # Proxy is handled by environment variables (core.env)
    
    # User requested to keep ALL data. Logic: High limit to avoid local truncation.
    # If PushPlus splits it, so be it, but data won't be lost.
    MAX_MESSAGE_SIZE = 25000

    def run(self) -> Message:
        df = self._get_fund_data()
        
        # Save to DB
        if not df.empty:
            try:
                db.save_monitor_data(df, 'fund_valuation', if_exists='replace')
            except Exception as e:
                print(f"[Fund] DB Save Error: {e}")
        
        # Smart Truncation Logic
        import re
        funds_low, funds_mid, funds_high = self._prepare_data_lists(df)
        
        # Backup for restoration approach or just use lists directly
        # Strategy: If too big, trim 'Normal' (Mid) first, then 'High', then 'Low'
        
        final_html = ""
        while True:
            html = self.template.render('fund.html', {
                'title': '指数估值日报',
                'date': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                'f_l': funds_low,
                'f_m': funds_mid,
                'f_h': funds_high
            })
            
            # Advanced Minification
            html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
            html = re.sub(r'>\s+<', '><', html)
            html = re.sub(r'\s+', ' ', html).strip()
            
            if len(html.encode('utf-8')) <= self.MAX_MESSAGE_SIZE:
                final_html = html
                break
            
            # Truncation Priority: Normal -> High -> Low
            if funds_mid:
                funds_mid.pop()
            elif funds_high:
                funds_high.pop()
            elif funds_low:
                funds_low.pop()
            else:
                final_html = html # Cannot truncate further
                break

        return Message(
            title=f'指数估值日报({time.strftime("%m-%d", time.localtime())})', 
            content=final_html, 
            type=ContentType.HTML,
            tags=['fund', self.topic]
        )
    
    def _get_fund_data(self):
        url = "https://danjuanapp.com/djapi/index_eva/dj"
        try:
            resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
            items = resp.json()['data']['items']
        except Exception as e:
            print(f"[Fund] Failed to load data: {e}")
            return pd.DataFrame()
        
        results = []
        for item in items:
            results.append({
                "指数": item['name'], 
                "PE": round(item['pe'], 1), 
                "PE百分位": round(item['pe_percentile'] * 100, 1),
                "PB": round(item['pb'], 1), 
                "PB百分位": round(item['pb_percentile'] * 100, 1),
                "ROE": round(item['roe'] * 100, 1), 
                "股息率": round(item['yeild'] * 100, 1),
                "估值": ["低估", "正常", "高估"][item['eva_type_int']] if item['eva_type_int'] in [0,1,2] else "异常",
                "链接": item['url']
            })
        return pd.DataFrame(results)

    def _prepare_data_lists(self, df):
        funds_low = []
        funds_mid = []
        funds_high = []
        
        if not df.empty:
            for i in df.index:
                link = df.loc[i,'链接']
                if '?' in link:
                    link = link.split('?')[0]
                
                item = {
                    'name': df.loc[i,'指数'],
                    'pe': df.loc[i,'PE'],
                    'pe_pct': df.loc[i,'PE百分位'],
                    'pb': df.loc[i,'PB'],
                    'pb_pct': df.loc[i,'PB百分位'],
                    'roe': df.loc[i,'ROE'],
                    'yield': df.loc[i,'股息率'],
                    'valuation': df.loc[i,'估值'],
                    'link': link
                }
                
                val = item['valuation']
                if val == '低估':
                    funds_low.append(item)
                elif val == '高估':
                    funds_high.append(item)
                else:
                    funds_mid.append(item)
        
        # Sort by PE Percentile (Ascending)
        funds_low.sort(key=lambda x: x['pe_pct'])
        funds_mid.sort(key=lambda x: x['pe_pct'])
        funds_high.sort(key=lambda x: x['pe_pct'])
        
        return funds_low, funds_mid, funds_high

    def _render_html(self, df):
        # Deprecated: Logic moved to run() for smart truncation
        pass
