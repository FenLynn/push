import akshare as ak
import pandas as pd
from .base import BaseIndicator

class M2Indicator(BaseIndicator):
    """M2 货币供应量"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_money_supply()
            # Parse month to date
            df['date'] = pd.to_datetime(df['月份'], format='%Y年%m月份')
            df = df.rename(columns={
                '货币和准货币(M2)-数量(亿元)': 'm2',
                '货币(M1)-数量(亿元)': 'm1',
                '流通中的现金(M0)-数量(亿元)': 'm0',
                '货币和准货币(M2)-同比增长': 'm2_growth'
            })
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"M2 Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Use 3:1 ratio layout
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Data windows - monthly data
        df_short = df.iloc[-12:].copy()    # Recent 12 months (1 year)
        df_long = df.iloc[-240:].copy()    # History 240 months (20 years)
        
        # Colors
        c_m2 = '#E74C3C'      # M2 - Red
        c_m1 = '#3498DB'      # M1 - Blue
        c_m0 = '#2ECC71'      # M0 - Green
        
        # --- Top: Recent (1 Year) - M2 with Growth Rate ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['m2']/10000, 'o-', color=c_m2,
                   linewidth=2, markersize=5, label='M2(万亿元)')
        
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(df_short['date'], df_short['m2_growth'], 'D-', color='orange',
                     linewidth=2, markersize=4, label='M2同比增长(%)')
        
        # Current value lines
        try:
            curr_m2 = df_short.iloc[-1]['m2'] / 10000
            curr_growth = df_short.iloc[-1]['m2_growth']
            self.plotter.draw_current_line(curr_m2, ax_top, c_m2)
            self.plotter.draw_current_line(curr_growth, ax_top_r, 'orange')
        except: pass
        
        # Format top
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r,
                             title='宏观数据-货币供应量M2 (近期)',
                             ylabel_left='M2(万亿元)',
                             ylabel_right='同比增长(%)',
                             rotation=15)
        self.plotter.set_no_margins(ax_top)
        self.plotter.set_no_margins(ax_top_r)
        
        # --- Bottom: History (20 Years) - M2 Growth Rate ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['m2_growth'], color=c_m2,
                   linewidth=1.5, label='M2同比增长(%)')
        ax_bot.fill_between(df_long['date'], df_long['m2_growth'], color=c_m2, alpha=0.3)
        ax_bot.axhline(y=0, color='black', linestyle='--', linewidth=0.8, alpha=0.5)
        
        # Format bottom with internal title
        self.plotter.fmt_single(fig, ax_bot,
                              title='历史走势 (20年)',
                              ylabel='M2同比增长(%)',
                              rotation=15)
        self.plotter.set_no_margins(ax_bot)
        
        # Save
        path = "output/finance/m2.png"
        self.plotter.save(fig, path)
        return path
