import akshare as ak
import pandas as pd
from .base import BaseIndicator

class PPIIndicator(BaseIndicator):
    """PPI 工业生产者出厂价格指数"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_ppi()
            # Parse month to date
            df['date'] = pd.to_datetime(df['月份'], format='%Y年%m月份')
            df = df.rename(columns={
                '当月': 'ppi',
                '当月同比增长': 'ppi_growth'
            })
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"PPI Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Use 3:1 ratio layout
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Data windows - monthly data
        df_short = df.iloc[-12:].copy()    # Recent 12 months (1 year)
        df_long = df.iloc[-240:].copy()    # History 240 months (20 years)
        
        # Colors
        c_ppi = '#9B59B6'        # PPI index - Purple
        c_growth = '#E67E22'     # Growth - Orange
        
        # --- Top: Recent (1 Year) - Dual Y-axis ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['ppi'], 'o-', color=c_ppi, 
                   linewidth=2, markersize=5, label='PPI指数')
        
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(df_short['date'], df_short['ppi_growth'], 'D-', color=c_growth,
                     linewidth=2, markersize=4, label='同比增长(%)')
        
        # Current value lines
        try:
            curr_ppi = df_short.iloc[-1]['ppi']
            curr_growth = df_short.iloc[-1]['ppi_growth']
            self.plotter.draw_current_line(curr_ppi, ax_top, c_ppi)
            self.plotter.draw_current_line(curr_growth, ax_top_r, c_growth)
        except: pass
        
        # Format top
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r,
                             title='宏观数据-PPI工业生产者价格指数 (近期)',
                             ylabel_left='PPI指数',
                             ylabel_right='同比增长(%)',
                             rotation=15)
        self.plotter.set_no_margins(ax_top)
        self.plotter.set_no_margins(ax_top_r)
        
        # --- Bottom: History (20 Years) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['ppi'], color=c_ppi, linewidth=1.5, label='PPI指数')
        ax_bot.fill_between(df_long['date'], 100, df_long['ppi'], 
                           where=(df_long['ppi']>=100), color=c_ppi, alpha=0.3)
        ax_bot.fill_between(df_long['date'], 100, df_long['ppi'],
                           where=(df_long['ppi']<100), color='gray', alpha=0.2)
        ax_bot.axhline(y=100, color='black', linestyle='--', linewidth=0.8, alpha=0.5)
        
        # Format bottom with internal title
        self.plotter.fmt_single(fig, ax_bot,
                              title='历史走势 (20年)',
                              ylabel='PPI指数',
                              rotation=15)
        self.plotter.set_no_margins(ax_bot)
        
        # Save
        path = "output/finance/ppi.png"
        self.plotter.save(fig, path)
        return path
