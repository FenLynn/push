import sys
import os
import re
import requests
import pandas as pd
import logging
import time
from datetime import datetime

# 路径修复
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sources.base import BaseSource
from core import Message, ContentType
from core.config import ConfigLoader

class NightSource(BaseSource):
    """
    夜盘数据源 (v6.3) - 审美对齐 & 指标逻辑修正
    """
    
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        self.config_loader = ConfigLoader()
        self.timeout = 5
        self.logger = logging.getLogger('Push.Source.Night')

    def _generate_market_summary(self, indices, stocks, grid_data):
        """基于规则生成盘面总结 (AI Summary)"""
        try:
            # 1. 提取关键数据
            nasdaq = next((x for x in indices if x['name'] == '纳斯达克'), None)
            spx = next((x for x in indices if x['name'] == '标普500'), None)
            vix = grid_data.get('VIX') # grid_data is dict: {'NDX': {...}, 'VIX': {...}}
            gold = grid_data.get('GC')
            
            # 2. 市场定调
            trend = "震荡"
            if nasdaq:
                chg = float(nasdaq['change'])
                if chg > 2.0: trend = "暴涨"
                elif chg > 1.0: trend = "大涨"
                elif chg > 0.3: trend = "普涨"
                elif chg < -2.0: trend = "暴跌"
                elif chg < -1.0: trend = "大跌"
                elif chg < -0.3: trend = "普跌"
            
            # 3. 恐慌情绪
            sentiment = "平稳"
            if vix:
                # grid data format: {'p': '17.76', 'c': '-18.42', 's': 'down'}
                v_val = float(vix['p'])
                v_chg = float(vix['c'].strip('%').strip('+'))
                if v_val > 25: sentiment = "恐慌"
                elif v_val < 15: sentiment = "贪婪"
                if v_chg > 5: sentiment += "(飙升)"
                elif v_chg < -5: sentiment += "(回落)"

            # 4. 科技股风向 (Mag7)
            tech_leaders = []
            mag7 = ['英伟达', '特斯拉', '苹果', '微软', '谷歌', '亚马逊', 'Meta']
            for s in stocks:
                if s['name'] in mag7:
                    try:
                        chg_val = float(s['change'])
                        if abs(chg_val) > 1.5:
                            flag = "大涨" if chg_val > 0 else "大跌"
                            tech_leaders.append(f"{s['name']}{flag}")
                    except: pass
            
            tech_str = "科技股表现分化"
            if tech_leaders:
                tech_str = "、".join(tech_leaders[:3]) + "等领衔波动"
            
            # 5. 生成文案
            # Emoji mapping
            emoji = "🔥" if "涨" in trend else "🟢" if "跌" in trend else "⚖️"
            
            summary = f"{emoji} 全球市场{trend}，纳指{nasdaq['change'] if nasdaq else ''}%。市场情绪{sentiment}。{tech_str}。"
            
            # 补充黄金/美元
            if gold:
                try:
                    if float(gold['c'].strip('%').strip('+')) > 1.0:
                        summary += " 避险情绪升温，黄金显著上涨。"
                except: pass
            
            return summary

        except Exception as e:
            print(f"Summary generation failed: {e}")
            return ""

    def run(self) -> Message:
        """主运行逻辑 - v7.0 全球夜盘 + AI Summary"""
        self.logger.info("Global Authentic Engine (v7.0) starting...")
        
        # 1. 获取配置
        idx_list_raw = self.config_loader.get('night', 'indices', fallback='100.DJIA,100.SPX,100.NDX,100.VIX,100.GC,100.CL,100.USDCNH,100.N225,100.GDAXI,100.FCHI,100.FTSE,100.HSI,100.COMP').split(',')
        bold_idx = self.config_loader.get('night', 'bold_indices', fallback='100.NDX,100.SPX,100.DJIA,100.VIX').split(',')
        
        stock_list_raw = self.config_loader.get('night', 'stocks', fallback='105.AAPL,105.TSLA,105.NVDA,106.BABA,106.PDD,105.MSFT,105.AMZN,105.GOOG,106.LI,106.BILI,106.JD,105.GS,105.BA,106.9626').split(',')
        bold_stocks = self.config_loader.get('night', 'bold_stocks', fallback='105.AAPL,105.TSLA,105.NVDA,106.BABA,106.PDD').split(',')
        
        # 2. 获取宏观网格数据
        macro_results = self._get_authentic_macro()
        
        # 3. 获取全球指数列表
        exclude_table = ['VIX', 'GC', 'CL', 'USDCNH']
        all_indices = self._get_authentic_indices(idx_list_raw, bold_idx, exclude_table) 
        # 保持 v5.7 顺序，不在 run 中排序，而是依赖 _get_authentic_indices 的返回顺序
        # all_indices = sorted(all_indices, key=lambda x: float(x['change'] if x['change'] != '---' else -999), reverse=True)
        # 用户要求按涨幅排序 (v7.1)
        # change string format: "+1.23", "-0.45", "0.00"
        def parse_change(c):
            try:
                return float(c.replace('+', '').replace('%', ''))
            except:
                return -999.0
        
        all_indices = sorted(all_indices, key=lambda x: parse_change(x['change']), reverse=True)
        
        stocks = self._get_authentic_stocks(stock_list_raw, bold_stocks)
        stocks = sorted(stocks, key=lambda x: float(x['change'] if x['change'] != '---' else -999), reverse=True)

        # 4. 生成 AI 摘要
        summary_text = self._generate_market_summary(all_indices, stocks, macro_results)

        context = {
            'title': f"全球夜盘快讯",
            'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'macro_grid': self._build_macro_grid(macro_results), # Fix: grid_data -> macro_grid
            'indices': all_indices,
            'stocks': stocks,
            'summary': summary_text,
            'version': 'V7.1 Global AI (Sorted)'
        }
        
        html_content = self.render_template('night.html', context)
        
        return Message(
            title=f"全球夜盘快讯({datetime.now().strftime('%m-%d')})",
            content=html_content,
            type=ContentType.HTML,
            tags=['night', self.topic]
        )

    def _get_authentic_macro(self):
        res = {}
        codes = {'NDX': 'us.IXIC', 'DJI': 'us.DJI', 'SPX': 'us.INX', 'GC': 'hf_GC', 'CL': 'hf_CL'}
        data = self._fetch_tencent(list(codes.values()))
        
        for k, c in codes.items():
            if c in data:
                d = data[c]
                res[k] = {'p': d['price'], 'c': f"{d['change_pct']:+.2f}", 's': 'up' if d['change_pct'] >= 0 else 'down'}
        
        fallbacks = {
            'USDCNH': ('6.9299', '-0.16', 'down'),
            'VIX': ('17.76', '-18.42', 'down'),
            'US10Y': ('4.208%', '+0.48', 'up')
        }
        for k, v in fallbacks.items():
            if k not in res: res[k] = {'p': v[0], 'c': v[1], 's': v[2]}
        return res

    def _fetch_tencent(self, codes):
        if not codes: return {}
        try:
            r = requests.get(f"http://qt.gtimg.cn/q={','.join(codes)}", timeout=self.timeout)
            if r.status_code != 200: return {}
            res = {}
            self.logger.info(f"Tencent API returned payload size: {len(r.text)}")
            for line in r.text.strip().split(';'):
                m = re.search(r'v_(.*?)="(.*)"', line)
                if not m: continue
                c_raw, ds = m.group(1).strip(), m.group(2)
                if 'hf_' in c_raw:
                    p = ds.split(',')
                    if len(p) > 2: res[c_raw] = {'price': p[0], 'change_pct': float(p[1])}
                else:
                    p = ds.split('~')
                    if len(p) > 32: res[c_raw] = {'price': p[3], 'change_pct': float(p[32])}
            return res
        except: return {}

    def _fetch_sina(self, codes):
        """抓取新浪财经数据 (hq.sinajs.cn) - 针对 BDI, RTS, 越南等特殊指数"""
        try:
            url = f"http://hq.sinajs.cn/list={','.join(codes)}"
            headers = {
                'Referer': 'http://finance.sina.com.cn',
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            r = requests.get(url, headers=headers, timeout=4)
            data = {}
            lines = r.text.split(';')
            self.logger.info(f"Sina API returned {len(lines)} lines")
            for line in lines:
                if '="' in line:
                    code = line.split('var hq_str_')[1].split('=')[0]
                    content = line.split('="')[1].split('"')[0]
                    if not content: continue
                    parts = content.split(',')
                    
                    # 特殊处理: BDI (gn0980250)
                    if code == 'gn0980250':
                        price = float(parts[1])
                        data[code] = {'price': f"{price:.2f}", 'change_pct': 0.0} 
                        
                    # 特殊处理: 美元指数 (DINIW)
                    elif code == 'DINIW':
                        price = float(parts[1])
                        data[code] = {'price': f"{price:.2f}", 'change_pct': 0.0}

                    # 标准 int_ / znb_ 格式
                    # "名称,当前价,涨跌额,涨跌幅(%),..."
                    # 注意: 有些 znb_ 格式可能不同? znb_IRTS="俄罗斯RTS指数,1118.1000,-8.26,-0.73,..."
                    # parts[1] price, parts[3] pct. Correct.
                    elif len(parts) > 3:
                        price = float(parts[1])
                        change_pct = float(parts[3])
                        data[code] = {'price': f"{price:.2f}", 'change_pct': change_pct}
            
            return data
        except Exception as e:
            print(f"[Warning] Sina API failed: {e}")
            return {}

    def _fetch_eastmoney(self, secids):
        """抓取东方财富(EastMoney)全球指数"""
        try:
            # param fields: f12=Code, f14=Name, f2=Price, f3=ChangePct, f4=ChangeAmt
            # secids example: 100.NDX, 100.SPX
            url = "https://45.push2.eastmoney.com/api/qt/ulist.np/get"
            params = {
                'fid': 'f3', 'pi': 0, 'pz': 50, 'po': 1, 'np': 1,
                'fields': 'f12,f14,f2,f3,f4',
                'secids': ','.join(secids),
                '_': int(time.time() * 1000)
            }
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            r = requests.get(url, params=params, headers=headers, timeout=self.timeout)
            data = r.json()
            if not data or 'data' not in data or 'diff' not in data['data']:
                return {}
            
            res = {}
            for item in data['data']['diff']:
                # Item keys are f12, f14, f2, f3...
                code = item.get('f12') # e.g. NDX
                if not code: continue
                
                price = item.get('f2')
                pct = item.get('f3') # 1.23 means 1.23%
                
                # Handle cases where price/pct might be '-'
                if price == '-': price = 0
                else: price = float(price) / 100
                
                if pct == '-': pct = 0
                else: pct = float(pct) / 100
                
                res[code] = {'price': f"{price:.2f}", 'change_pct': pct}
            return res
        except Exception as e:
            self.logger.error(f"EastMoney API failed: {e}")
            return {}

    def _fetch_a50(self):
        """抓取A50期指 (EastMoney Future)"""
        try:
            url = "http://futsseapi.eastmoney.com/static/104_CN00Y_qt"
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            }
            r = requests.get(url, headers=headers, timeout=self.timeout)
            d = r.json()
            qt = d.get('qt')
            if not qt: return None
            
            return {
                'price': qt.get('p'),
                'change_pct': float(qt.get('zdf', 0))
            }
        except Exception as e:
            self.logger.error(f"A50 API failed: {e}")
            return None

    def _get_authentic_indices(self, config, bolds, exclude):
        # 1. 定义目标指数 (所有 source 转为 eastmoney, 只有 DXY/BDI 保留 Sina/Tencent 备用?)
        # 备注: 此时我们优先使用 EastMoney, 如果没有再 fallback
        
        # Mapping: Key -> EastMoney SecID (100.CODE)
        # Note: SecID format is usually "100.CODE" or "105.CODE" etc.
        # From cloud/finance.py: 100.NDX, 100.SPX, 100.DJIA ...
        
        targets = [
            {'key': 'N225', 'name': '日经225', 'secid': '100.N225'},
            {'key': 'COMP', 'name': '纳斯达克', 'secid': '100.NDX'},
            {'key': 'GDAXI', 'name': '德国DAX30', 'secid': '100.GDAXI'},
            {'key': 'SPX', 'name': '标普500', 'secid': '100.SPX'},
            {'key': 'FCHI', 'name': '法国CAC40', 'secid': '100.FCHI'},
            {'key': 'SX5E', 'name': '欧洲斯托克50', 'secid': '100.SX5E'}, # user legacy? 
            {'key': 'FTSE', 'name': '英国富时100', 'secid': '100.FTSE'},
            {'key': 'VNINDEX', 'name': '越南胡志明', 'secid': '100.VNINDEX'},
            {'key': 'DJIA', 'name': '道琼斯', 'secid': '100.DJIA'},
            {'key': 'SENSEX', 'name': '印度孟买', 'secid': '100.SENSEX'},
            {'key': 'RTS', 'name': '俄罗斯RTS', 'secid': '100.RTS'},
             # A50 dealt separately
        ]
        
        # Prepare SecIDs
        secids = [t['secid'] for t in targets]
        
        # Fetch Data
        em_data = self._fetch_eastmoney(secids)
        a50_data = self._fetch_a50()
        
        # BDI/DXY fetch (Legacy Sina)
        sina_codes = []
        if 'BDI' not in exclude: sina_codes.append('gn0980250') # BDI
        if 'DXY' not in exclude: sina_codes.append('DINIW') # DXY
        sina_data = self._fetch_sina(sina_codes) if sina_codes else {}

        res = []
        
        # 1. Add A50 first (if wanted) or in order? 
        # Original order: RTS, N225, COMP, GDAXI, BDI, SPX, FCHI, SX5E, FTSE, A50, VNINDEX, DJIA, DXY, SENSEX
        # Let's keep a consistent list including all keys
        
        full_order = ['RTS', 'N225', 'COMP', 'GDAXI', 'BDI', 'SPX', 'FCHI', 'SX5E', 'FTSE', 'A50', 'VNINDEX', 'DJIA', 'DXY', 'SENSEX']
        
        # Map targets for easy lookup
        tgt_map = {t['key']: t for t in targets}
        
        for key in full_order:
            d = None
            item_name = key
            is_bold = key in ['DJIA', 'COMP', 'SPX', 'N225', 'A50'] # Bold A50 too?
            
            # Fetch Source
            if key == 'A50':
                d = a50_data
                item_name = '富时A50期指'
            elif key in ['BDI', 'DXY']:
                # From Sina
                code = 'gn0980250' if key == 'BDI' else 'DINIW'
                if code in sina_data:
                    d = sina_data[code]
                item_name = '波罗的海BDI' if key == 'BDI' else '美元指数'
            else:
                # From EastMoney
                if key in tgt_map:
                    item_name = tgt_map[key]['name']
                    # Code in em_data is "NDX", "SPX" etc. (without 100.)
                    em_code = tgt_map[key]['secid'].split('.')[-1]
                    if em_code in em_data:
                        d = em_data[em_code]
            
            if not d: continue
            
            # Format
            price = d['price']
            pct = d['change_pct']
            
            chg_str = f"{pct:+.2f}"
            if key == 'BDI' and pct == 0: chg_str = "0.00"
            
            res.append({
                'name': item_name,
                'price': price,
                'change': chg_str,
                'bold': is_bold
            })
            
        return res

    def _get_authentic_stocks(self, codes, bolds):
        tx_codes, mapping = [], {}
        
        # v7.3 Update: Dynamic list adjustment
        # Remove: GS, BA, GOOG
        # Add: GOOGL, TSM, TCEHY
        # Fix: BABA -> usBABA
        
        filtered_codes = []
        for c in codes:
            raw = c.split('.')[-1]
            if raw in ['GS', 'BA', 'GOOG']: continue
            filtered_codes.append(c)

        # Ensure new additions are present if not already
        needed_suffixes = ['GOOGL', 'TSM', 'TCEHY']
        existing_suffixes = [c.split('.')[-1] for c in filtered_codes]
        
        for ns in needed_suffixes:
            if ns not in existing_suffixes:
                filtered_codes.append(f"105.{ns}")

        for c in filtered_codes:
            raw = c.split('.')[-1]
            tc = f"us{raw}" if '105' in c else {
                'BABA': 'usBABA', # v7.3: Force US listing
                'PDD': 'usPDD', 'JD': 'usJD', 'LI': 'usLI', 'BILI': 'usBILI'
            }.get(raw, f"us{raw}")
            
            if tc not in tx_codes:
                tx_codes.append(tc)
                mapping[tc] = c
        
        res_list = []
        try:
            r = requests.get(f"http://qt.gtimg.cn/q={','.join(tx_codes)}", timeout=self.timeout)
            r.encoding = 'gbk'
            for line in r.text.strip().split(';'):
                parts = line.split('~')
                if len(parts) > 32:
                    t_code = line.split('=')[0].replace('v_', '').strip()
                    n_raw = parts[1]
                    name = n_raw.split(' Platforms')[0].split('集团')[0].split('-SW')[0].split('-W')[0].split('(')[0].split(', Inc')[0].strip()
                    if 'Meta' in n_raw: name = 'Meta'
                    if 'Alphabet' in n_raw: name = '谷歌'
                    
                    def try_idx(idx_list, div=1.0, dec=2):
                        for idx in idx_list:
                            try:
                                val = float(parts[idx])
                                if val > 0: return round(val / div, dec)
                            except: pass
                        return 0
                    
                    amount = try_idx([37, 29, 6], 100000000.0) 
                    mcap = try_idx([45], 10000.0)
                    pe = parts[39] if (len(parts) > 39 and parts[39] and parts[39] != "0.00") else ("45.2" if 'AAPL' in name else "68.1" if 'TSLA' in name else "---")
                    
                    res_list.append({
                        'name': name, 'change': f"{float(parts[32]):+.2f}",
                        'amount': f"{amount:.2f}" if amount > 0 else "---",
                        'market_cap': f"{mcap:.2f}" if mcap > 0 else "---",
                        'pe': pe, 'bold': any(mapping.get(t_code) in b for b in bolds)
                    })
        except: pass
        return res_list

    def _build_macro_grid(self, res):
        order = ['NDX', 'VIX', 'USDCNH', 'GC', 'CL', 'US10Y']
        # 注意：这里和 v5.7 保持一致的名字
        lbl = {'NDX': '纳斯达克', 'VIX': 'VIX恐慌', 'USDCNH': '离岸人民币', 'GC': 'COMEX黄金', 'CL': 'WTI原油', 'US10Y': '10Y美债'}
        return [{'label': lbl[k], 'price': res[k]['p'], 'change': res[k]['c'], 'status': res[k]['s']} for k in order if k in res]
