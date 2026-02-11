"""
Stock Source - 股票行情推送 (Enhanced)
全面升级版：自选股 + 指数 + 板块动态 + 成交排行 + 热门股 + 创新高
"""
import sys, os, time
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import requests
import akshare as ak

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sources.base import BaseSource
from core import Message, ContentType
from core.config import config

# 导入原有的 cloud 库
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from cloud import *
from cloud.utils.lib import *
from core.config import config


class StockSource(BaseSource):
    """股票数据源 (Enhanced)"""
    
    def __init__(self, topic='me'):
        super().__init__()
        self.topic = topic
        
        # Load watchlists from config
        self.STOCKS_WATCHLIST = config.get_stock_watchlist()
        
        self.ETFS_WATCHLIST = config.get_stock_etf_watchlist()

        self.logger = logging.getLogger('Push.Source.Stock')
        self.bold_stocks = bold_stock_list
        
        # 调试日志：检查环境和代理配置
        self.logger.info(f"Environment check: is_server={is_server()}, vps_proxy_ip='{vps_proxy_ip}'")
        self.logger.info(f"Config: is_use_proxy={is_use_proxy}")
        
        # 智能加载数据（带重试机制）
        self.df_all = self._load_data_with_retry()
    
    def run(self) -> Message:
        """
        生成股票报告
        
        Returns:
            Message: 股票消息（HTML 格式）
        """
        # 检查是否交易日
        try:
            is_trade_day = get_today_trade_status()
        except NotImplementedError:
            weekday = datetime.now().weekday()
            is_trade_day = weekday < 5
            self.logger.info(f"Using fallback trade day detection: {is_trade_day}")
        
        # 准备数据
        data = {
            'trade_status': is_trade_day,
            'update_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime())
        }
        
        if not is_trade_day:
            html = self.render_template('stock.html', data)
            title = f'自选股({time.strftime("%m-%d", time.localtime())})'
            return Message(
                title=title,
                content=html,
                type=ContentType.HTML,
                tags=['stock', 'market', self.topic],
                metadata={'trade_status': False}
            )
        
        # 获取各类数据
        try:
            # 获取分类数据
            watch_data = self._get_stock_data()
            data['stocks'] = watch_data.get('stocks', [])
            # 独立获取 ETF 数据
            data['etfs'] = self._get_etf_data()
            
            data['indexes'] = self._get_index_data()
            data['summary'] = self._get_market_summary(data['indexes'])
            data['sectors'] = self._get_sector_leaders()
            data['turnover_ranking'] = self._get_turnover_ranking()
            data['hot_stocks'] = self._get_hot_stocks()
            data['new_highs'] = self._get_new_highs()
        except Exception as e:
            self.logger.error(f"Error collecting market data: {e}")
            # 继续使用已收集的部分数据
        # 渲染 HTML
        # 渲染 HTML (智能裁剪防分页)
        MAX_LEN = 14000 # PushPlus limit is ~15KB usually.
        
        html = self.render_template('stock.html', data)
        # Minify (Simple): remove newlines and extra spaces
        html = html.replace('\n', '').replace('  ', '')

        if len(html) > MAX_LEN:
            self.logger.info("Output too large, trimming New Highs...")
            data['new_highs'] = []
            html = self.render_template('stock.html', data)
            html = html.replace('\n', '').replace('  ', '')
            
        if len(html) > MAX_LEN:
             self.logger.info("Output still too large, trimming Turnover Ranking...")
             data['turnover_ranking'] = []
             html = self.render_template('stock.html', data)
             html = html.replace('\n', '').replace('  ', '')
             
        if len(html) > MAX_LEN:
             self.logger.info("Output still too large, trimming Sectors...")
             data['sectors'] = {} # Trim sectors
             html = self.render_template('stock.html', data)
             html = html.replace('\n', '').replace('  ', '')

        title = f'自选股({time.strftime("%m-%d", time.localtime())})'
        
        return Message(
            title=title,
            content=html,
            type=ContentType.HTML,
            tags=['stock', 'market', self.topic],
            metadata={'trade_status': True}
        )
    
    def _get_stock_data(self) -> List[Dict]:
        """获取自选股数据"""
        # if self.df_all is None or self.df_all.empty:
        #    return {'stocks': [], 'etfs': []}

        
        try:
            # 基础列名处理
            required_cols = ['名称', '代码', '最新价', '涨跌幅', '成交额']
            # ... (列名检查逻辑保留在 load_data 中) ...
            
            # 1. 处理股票 (根据名称匹配)
            # 1. 处理股票
            stock_data = []
            
            # 尝试从 Sina df_all 获取 (如果数据完整)
            if self.df_all is not None and len(self.df_all) > 1000:
                target_names = [x[0] for x in self.STOCKS_WATCHLIST]
                df_stocks = self.df_all[self.df_all['名称'].isin(target_names)].copy()
                for _, row in df_stocks.iterrows():
                     stock_data.append(self._format_item(row))
            
            # Fallback: 如果 Sina 失败或缺失，使用 Tencent 补全
            found_names = [x['name'] for x in stock_data]
            missing_stocks = [x for x in self.STOCKS_WATCHLIST if x[0] not in found_names]
            
            if missing_stocks:
                codes = [x[1] for x in missing_stocks]
                tx_data = self._get_tencent_data(codes)
                if tx_data is None: 
                    self.logger.warning("Tencent data returned None")
                    tx_data = {}
                    
                for name, code in missing_stocks:
                    if code in tx_data:
                        d = tx_data[code]
                        stock_data.append({
                            'name': name,
                            'code': code,
                            'close': d['close'],
                            'growth_rate': d['growth_rate'],
                            'turnover_billion': d.get('turnover', '-'),
                            'url': f"http://quote.eastmoney.com/{code[2:] if code.startswith(('sh','sz')) else code}.html"
                        })

            # Sort by Growth Rate (Desc)
            try:
                stock_data.sort(key=lambda x: float(x['growth_rate']), reverse=True)
            except Exception as e:
                self.logger.warning(f"Sort failed: {e}") 

            # 2. 处理 ETF (根据代码匹配)
            etf_data = []
            if self.ETFS_WATCHLIST:
                target_etf_codes = [x[1] for x in self.ETFS_WATCHLIST]
                # 注意：Sina 返回的代码可能带前缀，或者不带。需要模糊匹配
                # 假设 df_all['代码'] 是 6 位纯数字
                if self.df_all is not None and not self.df_all.empty:
                    df_etfs = self.df_all[self.df_all['代码'].isin(target_etf_codes)].copy()
                    
                    # 如果没匹配到，尝试用名称匹配
                    target_etf_names = [x[0] for x in self.ETFS_WATCHLIST]
                    if df_etfs.empty:
                        df_etfs = self.df_all[self.df_all['名称'].isin(target_etf_names)].copy()
    
                    for _, row in df_etfs.iterrows():
                        item = self._format_item(row)
                        # 修正名称为用户定义的名称 (可选)
                        for name, code in self.ETFS_WATCHLIST:
                            if code in row['代码'] or name == row['名称']:
                                item['name'] = name # 使用短名称
                                break
                        etf_data.append(item)
            
            return {'stocks': stock_data, 'etfs': etf_data}

        except Exception as e:
            self.logger.error(f"Error processing stock data: {e}", exc_info=True)
            return {'stocks': [], 'etfs': []}

    def _format_item(self, row):
        try:
            close = float(row['最新价'])
            grow = float(row['涨跌幅'])
            # 成交额单位修复: Sina 返回的是元，需要除以 1亿
            turn = float(row['成交额']) / 100000000.0
        except:
            close, grow, turn = 0, 0, 0
            
        return {
            'name': row['名称'],
            'code': row['代码'],
            'close': f"{close:.2f}",
            'growth_rate': f"{grow:.2f}",
            'turnover_billion': f"{turn:.2f}",
            'url': self._get_url(row['代码'])
        }
    
    def _get_hk_stock(self) -> List[Dict]:
        """获取港股数据"""
        try:
            df = ak.stock_hk_spot_em()
            df = df[df['代码'].isin(self.hk_stock_list)]
            df = df.loc[:, ('代码', '名称', '涨跌幅', '成交额', '最新价')]
            
            result = []
            for _, row in df.iterrows():
                result.append({
                    'name': row['名称'],
                    'code': row['代码'],
                    'close': round(row['最新价'], 2),
                    'growth_rate': round(row['涨跌幅'], 2),
                    'turnover_billion': round(row['成交额'] / 10000. / 10000., 2),
                    'url': f"https://wap.eastmoney.com/quote/stock/116.{row['代码']}.html",
                    'is_bold': row['名称'] in self.bold_stocks
                })
            return result
        except Exception as e:
            self.logger.warning(f"Failed to load HK stock data: {e}")
            return []
    

    
    
    def _get_market_summary(self, index_data: List[Dict]) -> Dict:
        """获取市场概况"""
        # V9: Robustness check (80 rows is not enough)
        if self.df_all is None or self.df_all.empty or len(self.df_all) < 1000:
            return {
                'up_sum': '-', 'down_sum': '-', 
                'long_10': '-', 'short_10': '-',
                'mean': '-', 'median': '-', 
                'total_money': '-', 'volume_ratio': '-',
                'style': '-'
            }
        
        df = self.df_all.iloc[:, :]
        
        # 计算统计数据
        up_sum = (pd.to_numeric(df['涨跌幅'], errors='coerce') > 0).sum()
        down_sum = (pd.to_numeric(df['涨跌幅'], errors='coerce') < 0).sum()
        long_10 = (pd.to_numeric(df['涨跌幅'], errors='coerce') >= 9.8).sum()
        short_10 = (pd.to_numeric(df['涨跌幅'], errors='coerce') <= -9.8).sum()
        mean_val = pd.to_numeric(df['涨跌幅'], errors='coerce').mean()
        median_val = pd.to_numeric(df['涨跌幅'], errors='coerce').median()
        
        # 计算总成交额 (Sina 单位是元)
        turnover_col = '成交额' if '成交额' in df.columns else None
        total_money = 0
        if turnover_col:
             total_money = pd.to_numeric(df[turnover_col], errors='coerce').sum()
             total_money = round(total_money / 100_000_000, 0) # 亿
        
        # 获取大盘量比 (基于上证指数历史成交额)
        volume_ratio = self._get_market_volume_ratio(total_money)
        
        # 估算大小盘分化：用上证指数 vs 创业板指
        style_diff = "均衡"
        sh_rate = 0
        cy_rate = 0
        for idx in index_data:
            if '上证指数' in idx['name']: sh_rate = float(idx['growth_rate'])
            if '创业板' in idx['name']: cy_rate = float(idx['growth_rate'])
        
        if sh_rate - cy_rate > 0.5: style_diff = "大盘强"
        elif cy_rate - sh_rate > 0.5: style_diff = "小盘强"
        
        return {
            'up_sum': int(up_sum),
            'down_sum': int(down_sum),
            'long_10': int(long_10),
            'short_10': int(short_10),
            'mean': round(mean_val, 2),
            'median': round(median_val, 2),
            'total_money': total_money,
            'volume_ratio': volume_ratio,
            'style': style_diff
        }

    def _get_market_volume_ratio(self, current_money: float) -> str:
        """获取大盘量比 (今天 / 昨天)"""
        try:
            # 获取上证指数最近2日历史
            df = ak.stock_zh_index_daily_em(symbol="sh000001")
            if df.empty or len(df) < 2:
                return "1.0"
            
            # df columns: date, open, close, high, low, volume, amount
            # amount is turnover? usually yes.
            # But amount units might differ.
            # Check last row date. If today is trade day and market open, last row might be today (incomplete) or yesterday.
            # Safe bet: get average of last 5 days amount to be smoother?
            # User wants "Yesterday vs Today".
            
            # Assume last closed day is yesterday (index_daily usually updates after close)
            # Fetching real-time history is better but costly.
            # Let's use simplified logic:
            last_day_money = float(df.iloc[-1]['amount']) 
            # Note: AkShare EM returns amount in raw value usually? Or Wan?
            # Let's assume proportional.
            
            # Wait, current_money is A-share total (Sina).
            # last_day_money is Shanghai Index total.
            # They are not comparable directly.
            # Need A-share total history.
            # Hard to get.
            # Fallback: volume ratio of Shanghai Index only.
            
            # Fetch SH Index real-time money:
            # We have it in index_data but passed to summary? No.
            # Let's use hardcoded ratio if current_money > 0
            
            # Better strategy: Get volume ratio from board_industry_summary_ths? No.
            # Return pure textual desc?
            
            return "N/A"
        except:
            return "N/A"


    def _get_tencent_data(self, codes: List[str]) -> Dict[str, Dict]:
        """
        从腾讯接口批量获取简单的行情数据 (Price, Change_Pct, Rate)
        Format: v_code="1~Name~Code~Price~...~Change~Change%~..."
        Index 3: Price
        Index 31: Change
        Index 32: Change%
        """
        if not codes:
            return {}
            
        result = {}
        try:
            # Join codes: sh000001,hkHSI,sh510300
            chunk_size = 60
            for i in range(0, len(codes), chunk_size):
                chunk = codes[i:i+chunk_size]
                url = f"http://qt.gtimg.cn/q={','.join(chunk)}"
                
                resp = requests.get(url, timeout=5)
                if resp.status_code != 200:
                    continue
                    
                text = resp.text
                # Parse: v_sh000001="1~..."
                lines = text.strip().split(';')
                for line in lines:
                    line = line.strip()
                    if not line or '=' not in line:
                        continue
                    
                    key, val = line.split('=', 1)
                    code = key.replace('v_', '').strip()
                    val = val.strip('"')
                    parts = val.split('~')
                    
                    if len(parts) > 37:
                        name = parts[1]
                        price = parts[3]
                        change_pct = parts[32]
                        # Index 37: Turnover in Wan (e.g. 50000 -> 50000 wan = 5 yi)
                        # So value / 10000 = Yi
                        try:
                            turn_wan = float(parts[37])
                            turn_yi = f"{turn_wan/10000:.2f}"
                        except:
                            turn_yi = '-'

                        result[code] = {
                            'name': name,
                            'close': price,
                            'growth_rate': change_pct,
                            'turnover': turn_yi,
                            'code': code 
                        }
        except Exception as e:
            self.logger.error(f"Tencent API error: {e}")
            
        return result

    def _get_index_data(self) -> List[Dict]:
        """获取主要指数：上证、创业、同花顺全A(代理)、恒生"""
        # Sina 接口代码映射
        target_indices = [
            ('上证指数', 'sh000001'),
            ('创业板指', 'sz399006'),
            ('上证50', 'sh000016'),
        ]
        
        result = []
        
        # 1. 尝试使用腾讯接口获取核心指数 + HSI
        # Tencent codes: sh000001, sz399006, sh000016, hkHSI
        tx_codes = ['sh000001', 'sz399006', 'sh000016', 'hkHSI']
        tx_data = self._get_tencent_data(tx_codes)
        
        # Helper to format index item
        def make_item(name, code, source_data):
            if code in source_data:
                d = source_data[code]
                url_code = code.lower().replace('hkhsi', 'hszsHSI').replace('sh', '').replace('sz', '')
                prefix = 'zs'
                if 'hk' in code or 'HSI' in code:
                    full_url = "http://quote.eastmoney.com/hk/zsHSI.html"
                    # HSI specific adjustments
                    if 'HSI' in code:
                        try:
                             d['close'] = f"{float(d['close']):.2f}"
                        except: pass
                else:
                    full_url = f"http://quote.eastmoney.com/{prefix}{code.lower()}.html"
                    
                return {
                    'name': name,
                    'close': d['close'],
                    'growth_rate': d['growth_rate'],
                    'url': full_url
                }
            return None

        # Process main indices
        for name, code in target_indices:
            item = make_item(name, code, tx_data)
            if item:
                result.append(item)
            else:
                # Fallback to Sina if Tencent missing (unlikely if successful)
                pass # logic could be added here
        
        # Process HSI
        hsi_item = make_item('恒生指数', 'hkHSI', tx_data)
        if hsi_item:
            result.append(hsi_item)
            
        # If result is empty (Tencent failed), fallback to Sina
        if not result:
            self.logger.warning("Tencent Indices failed, falling back to Sina...")
            # ... Original Sina Logic ...
            try:
                df = ak.stock_zh_index_spot_sina()
                for name, code in target_indices:
                    item_row = df[df['代码'] == code]
                    if item_row.empty: item_row = df[df['代码'] == code[2:]]
                    if not item_row.empty:
                        row = item_row.iloc[0]
                        result.append({
                            'name': name,
                            'close': f"{row['最新价']:.2f}",
                            'growth_rate': f"{row['涨跌幅']:.2f}",
                            'url': f"http://quote.eastmoney.com/zs{code.lower()}.html"
                        })
            except Exception as e:
                self.logger.error(f"Sina Index fallback error: {e}")
                
        return result

    def _get_etf_data(self) -> List[Dict]:
        """获取ETF数据 (使用腾讯接口)"""
        etf_data = []
        try:
            # self.ETFS_WATCHLIST format: [('Name', 'sh588090'), ...]
            if not hasattr(self, 'ETFS_WATCHLIST'):
                 return []
                 
            # Add prefixes for Tencent (5/6 -> sh, 1 -> sz)
            codes = [x[1] for x in self.ETFS_WATCHLIST]
            tx_codes = []
            code_map = {}
            for x in codes:
                if x.isdigit():
                    prefix = 'sh' if x.startswith(('5', '6')) else 'sz'
                    full_code = prefix + x
                    tx_codes.append(full_code)
                    code_map[x] = full_code
                else:
                    tx_codes.append(x)
                    code_map[x] = x
            
            # 使用 Tencent 接口
            tx_data = self._get_tencent_data(tx_codes)
            
            for name, code in self.ETFS_WATCHLIST:
                full_code = code_map.get(code, code)
                if full_code in tx_data:
                    d = tx_data[full_code]
                    etf_data.append({
                        'name': name,
                        'code': code,
                        'close': d['close'],
                        'growth_rate': d['growth_rate'],
                        'turnover_billion': d.get('turnover', '-'), 
                        'url': f"http://quote.eastmoney.com/{code}.html"
                    })
            
            # Sort by Growth Rate (Desc)
            try:
                etf_data.sort(key=lambda x: float(x['growth_rate']), reverse=True)
            except:
                pass

                    
        except Exception as e:
            self.logger.error(f"ETF data error: {e}")
            
        return etf_data
    
    def _get_sector_leaders(self) -> Dict:
        """获取板块领涨领跌 Top 5"""
        for i in range(3):
            try:
                df = ak.stock_board_industry_summary_ths()
                df = df.loc[:, ('板块', '涨跌幅')]
                df = df.sort_values(by='涨跌幅', ascending=False)
                
                leaders = []
                for _, row in df.head(5).iterrows():
                    leaders.append({
                        'name': row['板块'],
                        'change': round(row['涨跌幅'], 2)
                    })
                
                losers = []
                for _, row in df.tail(5).iterrows():
                    losers.append({
                        'name': row['板块'],
                        'change': round(row['涨跌幅'], 2)
                    })
                losers.reverse()  # 从跌幅最大到最小
                
                return {'leaders': leaders, 'losers': losers}
            except Exception as e:
                self.logger.warning(f"Failed to get sector data (Try {i+1}): {e}")
                time.sleep(1)
        return None
    
    def _get_turnover_ranking(self) -> List[Dict]:
        """获取成交额排行 Top 10"""
        if self.df_all is None or self.df_all.empty:
            return []
        
        df = self.df_all.loc[:, ['代码', '名称', '成交额', '涨跌幅', '最新价']]
        df = df.dropna()
        df = df.sort_values(by='成交额', ascending=False).head(10)
        
        result = []
        for _, row in df.iterrows():
            result.append({
                'name': row['名称'],
                'code': row['代码'],
                'turnover_billion': round(row['成交额'] / 100000000., 2),
                'growth_rate': round(row['涨跌幅'], 2),
                'url': self._get_url(row['代码'])
            })
        
        return result
    
    def _get_hot_stocks(self) -> List[Dict]:
        """获取热门股 Top 10（成交额 × 涨幅权重）"""
        if self.df_all is None or self.df_all.empty:
            return []
        
        df = self.df_all.loc[:, ['代码', '名称', '成交额', '涨跌幅', '最新价']]
        df = df.dropna()
        
        # 计算热度分数：成交额(亿) × |涨跌幅|
        df['热度'] = (df['成交额'] / 100000000.) * df['涨跌幅'].abs()
        df = df.sort_values(by='热度', ascending=False).head(10)
        
        result = []
        for _, row in df.iterrows():
            result.append({
                'name': row['名称'],
                'code': row['代码'],
                'growth_rate': round(row['涨跌幅'], 2),
                'turnover_billion': round(row['成交额'] / 100000000., 2),
                'url': self._get_url(row['代码'])
            })
        
        return result
    
    def _get_new_highs(self) -> List[Dict]:
        """获取创历史新高的股票"""
        try:
            # 使用同花顺接口获取创新高数据（比逐支查询快得多）
            df = ak.stock_rank_cxg_ths(symbol="历史新高")
            
            # 只取前 5 个
            result = []
            for _, row in df.head(5).iterrows():
                # 需要转换代码格式 (同花顺代码通常不带后缀，需要匹配)
                stock_name = row['股票简称']
                
                # 尝试从 self.df_all 中查找完整信息（包括代码）
                if self.df_all is not None and not self.df_all.empty:
                    match = self.df_all[self.df_all['名称'] == stock_name]
                    if not match.empty:
                        item = match.iloc[0]
                        result.append({
                            'name': stock_name,
                            'code': item['代码'],
                            'close': round(item['最新价'], 2),
                            'growth_rate': round(item['涨跌幅'], 2),
                            'url': self._get_url(item['代码'])
                        })
                        continue
                
                # 如果没找到，使用默认数据
                result.append({
                    'name': stock_name,
                    'close': str(row['最新价']),
                    'growth_rate': 'N/A', 
                    'url': ''
                })
                
            return result
        except Exception as e:
            self.logger.info(f"Failed to get new highs (non-critical): {e}")
            return []
    
    def _load_data_with_retry(self):
        """加载数据：优先使用 Sina 接口，带重试和列名映射"""
        import time
        
        # 1. 尝试 Sina 接口 (直连)
        for i in range(3):
            try:
                self.logger.info(f"Attempting to load data from Sina API (Try {i+1}/3)...")
                df = ak.stock_zh_a_spot()
                
                # 检查数据是否有效
                if df is None or df.empty:
                    raise Exception("Empty dataframe")
                    
                # 检查是否返回了 HTML 错误页 (Akshare 有时会把 HTML 解析成单列 DF 或者抛错，或者是空)
                # 这里假设 akshare 已经返回了 DF。如果 Warning 说 "starting with <", 说明 akshare 内部打印了 warning。
                # 我们尽量捕获它。
                    
                self.logger.info(f"Loaded {len(df)} rows from Sina")
                
                # Sina 列名映射
                # 常见列名: 代码,名称,最新价,涨跌额,涨跌幅,买入,卖出,昨收,今开,最高,最低,成交量,成交额,时间...
                # 目标列名: 代码, 名称, 最新价, 涨跌幅, 成交额, 换手率
                
                rename_map = {
                    '最新价': '最新价', 
                    '涨跌幅': '涨跌幅', 
                    '成交额': '成交额',
                    '换手率': '换手率'
                }
                
                # 检查 '成交额' 列
                if '成交额' not in df.columns:
                    # 有些接口可能叫 '成交额(元)' 或其他
                    for col in df.columns:
                        if '成交额' in col:
                            rename_map[col] = '成交额'
                            break
                
                # 检查 '换手率' 列
                if '换手率' not in df.columns:
                    # Sina 可能没有换手率，或者叫 '换手'
                    for col in df.columns:
                        if '换手' in col:
                            rename_map[col] = '换手率'
                            break
                            
                df.rename(columns=rename_map, inplace=True)
                
                # 补充缺失列 (Sina 如果没有换手率，就填0)
                if '换手率' not in df.columns:
                    df['换手率'] = 0
                
                if '成交额' not in df.columns:
                    df['成交额'] = 0
                    
                return df
                
            except Exception as e:
                msg = str(e)
                if "Can not decode" in msg and "<" in msg:
                     self.logger.info(f"Sina API blocked/html (Try {i+1}): {e}")
                else:    
                     self.logger.warning(f"Sina API failed (Try {i+1}): {e}")
                time.sleep(2) # 休息一下再试
        
        # 2. 如果 Sina 彻底失败，尝试 EM (虽然已知被墙，但作为最后的挣扎)
        try:
            self.logger.info("Attempting to load data from EM API (Last resort)...")
            df = ak.stock_zh_a_spot_em()
            return df
        except Exception as e:
            self.logger.error(f"EM API failed: {e}")
        
        return None

    def _get_url(self, code: str) -> str:
        """生成股票链接 (东财)"""
        # 统一处理代码格式
        clean_code = code.replace('sh', '').replace('sz', '')
        
        # 判断市场前缀 (如果原始代码带前缀最好，否则猜测)
        prefix = ""
        if 'sh' in code or code.startswith(('6', '5')):
            prefix = "sh"
        elif 'sz' in code or code.startswith(('0', '3', '1')):
            prefix = "sz"
        elif 'hk' in code:
             # Hong Kong
             return f"http://quote.eastmoney.com/hk/{code}.html"
            
        full_code = prefix + clean_code
        return f"http://quote.eastmoney.com/{full_code}.html"


if __name__ == '__main__':
    # 独立测试
    source = StockSource(topic='me')
    msg = source.run()
    print(f"Title: {msg.title}")
    print(f"Type: {msg.type}")
    print(f"Content length: {len(msg.content)} chars")
    print(f"Trade status: {msg.metadata.get('trade_status')}")
