import akshare as ak
import pandas as pd
from .base import BaseIndicator
from datetime import datetime, timedelta

class MarginIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        """Fetch Margin Data from SSE + Index Data"""
        import time
        try:
            # Calculate date range (past 3 years for margin data)
            end_date = datetime.now().strftime('%Y%m%d')
            start_date = (datetime.now() - timedelta(days=1100)).strftime('%Y%m%d')
            
            # 1. Get SSE Margin Data (most stable source)
            df_margin = ak.stock_margin_sse(start_date=start_date, end_date=end_date)
            df_margin = df_margin.rename(columns={
                '信用交易日期': 'date',
                '融资余额': '融资余额',
                '融资买入额': '融资买入额'
            })
            df_margin['date'] = pd.to_datetime(df_margin['date'], format='%Y%m%d')
            
            # 2. Get SSE Index for reference
            df_sh = ak.index_zh_a_hist(symbol="000001", period="daily")
            df_sh = df_sh[['日期', '收盘', '成交额']].rename(columns={
                '日期': 'date', 
                '收盘': 'sh_close', 
                '成交额': 'sh_vol'
            })
            df_sh['date'] = pd.to_datetime(df_sh['date'])
            
            # 3. Get SZSE Index for turnover
            df_sz = ak.index_zh_a_hist(symbol="399001", period="daily")
            df_sz = df_sz[['日期', '成交额']].rename(columns={
                '日期': 'date', 
                '成交额': 'sz_vol'
            })
            df_sz['date'] = pd.to_datetime(df_sz['date'])
            
            # 4. Merge all data
            df = pd.merge(df_margin, df_sh, on='date', how='left')
            df = pd.merge(df, df_sz, on='date', how='left')
            df = df.sort_values('date')
            
            # Calculate total market turnover and ratio
            df['total_vol'] = df['sh_vol'].fillna(0) + df['sz_vol'].fillna(0)
            df['margin_buy_ratio'] = df['融资买入额'] / df['total_vol'].replace(0, 1)
            
            self.logger.info(f"Margin data fetched: {len(df)} rows (SSE only, SZSE API unstable)")
            return df
            
        except Exception as e:
            self.logger.error(f"Margin Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Use 3:1 ratio layout
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Data windows
        df_short = df.iloc[-250:].copy()   # Recent 1 year
        df_long = df.iloc[-750:].copy()    # History ~3 years (margin data limited)
        
        # --- Top: Margin Balance vs Index (Recent) ---
        ax_top = axes[0]
        s_bal = df_short['融资余额'] / 100000000  # Convert to billions
        s_idx = df_short['sh_close']
        
        ax_top.plot(df_short['date'], s_bal, color='darkorange', 
                   linewidth=2, label='融资余额(亿)')
        
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(df_short['date'], s_idx, color='gray', 
                     linewidth=1.5, linestyle='--', label='上证指数')
        
        # Current value line
        self.plotter.draw_current_line(s_bal.iloc[-1], ax_top, 'darkorange')
        
        # Format top
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, 
                             title='市场情绪-融资余额 (近期)',
                             ylabel_left='余额(亿)', 
                             ylabel_right='点位',
                             rotation=15)
        self.plotter.set_no_margins(ax_top)
        self.plotter.set_no_margins(ax_top_r)
        
        # --- Bottom: Margin Buy Ratio (History) ---
        ax_bot = axes[1]
        s_ratio = df_long['margin_buy_ratio'] * 100
        
        ax_bot.fill_between(df_long['date'], s_ratio, 
                           color='cornflowerblue', alpha=0.4)
        ax_bot.plot(df_long['date'], s_ratio, 
                   color='cornflowerblue', linewidth=1.5, 
                   label='融资买入占比(%)')
        
        # Current value line
        self.plotter.draw_current_line(s_ratio.iloc[-1], ax_bot, 'cornflowerblue')
        
        # Format bottom with internal title
        self.plotter.fmt_single(fig, ax_bot, 
                              title='历史走势 (买入占比)',
                              ylabel='占比(%)', 
                              rotation=15)
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/margin.png"
        self.plotter.save(fig, path)
        return path
