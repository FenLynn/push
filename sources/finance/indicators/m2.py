import akshare as ak
import pandas as pd
from .base import BaseIndicator

class M2Indicator(BaseIndicator):
    """M2 货币供应量"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_money_supply()
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
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: 20 years (240 months)
        df_long = df.iloc[-240:].copy() 
        
        c_m2 = '#E74C3C'     # M2 - Red
        c_growth = '#273c75' # Growth - Energy Blue
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['m2']/10000, 'o-', color=c_m2,
                   linewidth=3, markersize=8, label='M2(万亿元)')
        
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(df_short['date'], df_short['m2_growth'], 'D-', color=c_growth,
                     linewidth=2.5, markersize=7, label='M2同比增长(%)')
        
        self.plotter.draw_current_line(df_short.iloc[-1]['m2']/10000, ax_top, c_m2)
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r,
                             title='宏观数据-货币供应量M2 (近期13月)',
                             ylabel_left='M2(万亿元)',
                             ylabel_right='同比增长(%)',
                             rotation=15,
                             data_left=df_short['m2']/10000,
                             data_right=df_short['m2_growth'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['m2_growth'], color=c_growth, linewidth=2)
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['m2_growth'], color=c_growth)
        ax_bot.axhline(y=0, color='#636e72', linestyle='--', linewidth=0.8, alpha=0.5)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年)', ylabel='M2 YoY(%)', rotation=15, 
                               data=df_long['m2_growth'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/m2.png"
        self.plotter.save(fig, path)
        return path
