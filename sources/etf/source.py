import logging
import time
import pandas as pd
import requests
import akshare as ak
from core import Message, ContentType, engine
from core.template import TemplateEngine
from core.config import config
from core.db import db
from sources.base import BaseSource

class ETFSource(BaseSource):
    """
    ETF Monitoring Source V2.0 (Premium Dashboard Edition)
    """
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.ETF')
        self.template_engine = TemplateEngine()
        self.db = db

    def _get_tencent_data(self, codes):
        if not codes: return {}
        result = {}
        try:
            formatted_codes = []
            for c in codes:
                if c.startswith(('sh', 'sz')): formatted_codes.append(c)
                else: formatted_codes.append(('sh' if c.startswith(('51', '60', '000001')) else 'sz') + c)
            
            url = f"http://qt.gtimg.cn/q={','.join(formatted_codes)}"
            resp = requests.get(url, timeout=5)
            if resp.status_code == 200:
                lines = resp.text.strip().split(';')
                for line in lines:
                    line = line.strip()
                    if '=' not in line: continue
                    key, val = line.split('=', 1)
                    code_long = key.replace('v_', '').strip()
                    parts = val.strip('"').split('~')
                    if len(parts) > 37:
                        result[code_long] = {
                            'name': parts[1].strip(),
                            'close': parts[3].strip(),
                            'growth_rate': parts[32].strip(),
                            'turnover': round(float(parts[37])/10000.0, 1) if parts[37] else 0,
                            'quantity_ratio': float(parts[49]) if len(parts) > 49 and parts[49] else 0.0
                        }
        except Exception as e:
            self.logger.error(f"Tencent API error: {e}")
        return result

    def _fetch_data(self):
        codes = config.get_etf_list()
        # Add SSEC (sh000001) and ChiNext (sz399006)
        all_codes = codes + ['sh000001', 'sz399006']
        data = self._get_tencent_data(all_codes)
        
        market_info = {}
        if 'sh000001' in data:
            market_info['sh'] = data.pop('sh000001')
        if 'sz399006' in data:
            market_info['sz'] = data.pop('sz399006')
        
        df_list = []
        for code_long, info in data.items():
            code = code_long[-6:] 
            df_list.append({
                '代码': code,
                '名称': info['name'],
                '最新价': float(info['close']),
                '涨跌幅': float(info['growth_rate']),
                '成交额_亿': info['turnover'],
                '量比': info['quantity_ratio']
            })
        
        df = pd.DataFrame(df_list)
        if not df.empty:
            df = df.sort_values(by='涨跌幅', ascending=False)
            # Use 'replace' to handle schema changes (new '量比' column)
            self.db.save_monitor_data(df, 'etf_monitor', if_exists='replace')
            
        return df, market_info

    def _get_sector(self, name):
        sectors = {
            '宽基': ['300', '50', '500', '1000', '恒生', 'A50', '纳指', '标普', '中概', '创业'],
            '科技': ['芯片', '半导体', '软件', '计算机', '游戏', '传媒', '互联', '通信', '数据', '人工智能', '科创'],
            '新能源': ['光伏', '电力', '锂电', '电池', '煤炭', '有色', '化工', '钢铁', '硅'],
            '大消费': ['医药', '医疗', '药', '养殖', '畜牧', '消费', '食品', '白酒', '农业', '白马'],
            '金融红利': ['银行', '证券', '券商', '保险', '地产', '房地产', '红利', '国企', '央企', '基建']
        }
        for s_name, keywords in sectors.items():
            for k in keywords:
                if k in name: return s_name
        return '其他'

    def _get_active_badge(self, vol, ratio):
        # 1. Safety Check (Absolute Liquidity)
        if vol < 0.2: return '冷清'
        # 2. Relative Activity (Volume Ratio)
        if ratio >= 2.0: return '放量'
        if ratio <= 0.6: return '缩量'
        return None

    def _render_html(self, df, market_info):
        sector_data = {}
        if not df.empty:
            for _, row in df.iterrows():
                name = row['名称']
                companies = ['华泰柏瑞', '易方达', '华夏', '南方', '嘉实', '博时', '广发', '汇添富', '国泰', '鹏华', '华安', '富国', '天弘', '工银', '招商', '大成', '银华', '华宝', '工银瑞信', '景顺长城']
                for c in companies: name = name.replace(c, '')
                name = name.strip()
                
                sector_label = self._get_sector(name)
                if sector_label not in sector_data: sector_data[sector_label] = []
                
                sector_data[sector_label].append({
                    'code': row['代码'],
                    'name': name,
                    'price': row['最新价'],
                    'change': row['涨跌幅'],
                    'volume': row['成交额_亿'],
                    'ratio': row['量比'],
                    'badge': self._get_active_badge(row['成交额_亿'], row['量比'])
                })

        # Calculate Max Vol Name (Cleaned)
        max_vol_name = 'N/A'
        if not df.empty:
            raw_top = df.sort_values('成交额_亿', ascending=False).iloc[0]['名称']
            for c in companies: raw_top = raw_top.replace(c, '')
            max_vol_name = raw_top.strip()

        stats = {
            'avg_change': round(df['涨跌幅'].mean(), 2) if not df.empty else 0,
            'up_count': len(df[df['涨跌幅'] > 0]) if not df.empty else 0,
            'down_count': len(df[df['涨跌幅'] < 0]) if not df.empty else 0,
            'flat_count': len(df[df['涨跌幅'] == 0]) if not df.empty else 0,
            'max_vol': max_vol_name,
            'total_vol': round(df['成交额_亿'].sum(), 1) if not df.empty else 0
        }

        # Calculate Sector Performance
        best_sec_name, best_sec_chg = '-', 0
        if sector_data:
            sec_perfs = []
            for sec, items in sector_data.items():
                if not items: continue
                avg = sum([x['change'] for x in items]) / len(items)
                sec_perfs.append((sec, avg))
            if sec_perfs:
                sec_perfs.sort(key=lambda x: x[1], reverse=True)
                best_sec_name, best_sec_chg = sec_perfs[0]
                best_sec_chg = round(best_sec_chg, 2)
        
        stats['top_sector'] = best_sec_name
        stats['top_sector_chg'] = best_sec_chg

        return self.template_engine.render('etf.html', {
            'title': 'ETF 监控',
            'date': time.strftime("%Y-%m-%d %H:%M:%S"),
            'market': market_info,
            'stats': stats,
            'sectors': sector_data
        })

    def _minify_html(self, html):
        """Simple HTML minifier to reduce payload size"""
        return "".join([line.strip() for line in html.splitlines() if line.strip()])

    def run(self):
        self.logger.info("Fetching ETF V2.0 Premium Dashboard Data...")
        df, market_info = self._fetch_data()
        html_content = self._render_html(df, market_info)
        
        # Minify to ensure fit in single PushPlus message (20kb limit)
        minified_content = self._minify_html(html_content)
        
        return Message(
            title="ETF 监控",
            content=minified_content,
            type=ContentType.HTML
        )
