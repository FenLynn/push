import akshare as ak
import pandas as pd
from .base import BaseIndicator

class OilIndicator(BaseIndicator):
    """中国成品油价调整"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.energy_oil_hist()
            df = df.rename(columns={'调整日期': 'date', '汽油价格': 'gasoline', '柴油价格': 'diesel'})
            df['date'] = pd.to_datetime(df['date'])
            df['gasoline'] = pd.to_numeric(df['gasoline'], errors='coerce')
            df['diesel'] = pd.to_numeric(df['diesel'], errors='coerce')
            return df.dropna(subset=['gasoline']).sort_values('date')
        except Exception as e:
            self.logger.error(f"Oil Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show 200 adjustments
        df_long = df.iloc[-200:].copy() 
        
        c1 = '#E74C3C' # Red
        c2 = '#2980B9' # Blue
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.step(df_short['date'], df_short['gasoline'], where='post', color=c1, linewidth=3, label='汽油价格')
        ax_top.step(df_short['date'], df_short['diesel'], where='post', color=c2, linewidth=3, label='柴油价格')
        
        self.plotter.fmt_single(fig, ax_top, title='行业数据-中国油价变动 (近期13月)', 
                              ylabel='元/吨', rotation=15, data=[df_short['gasoline'], df_short['diesel']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['gasoline'], color=c1, alpha=0.9, linewidth=1.5, label='汽油')
        ax_bot.plot(df_long['date'], df_long['diesel'], color=c2, alpha=0.9, linewidth=1.5, label='柴油')
        
        # Remove historical fill as requested in previous turn
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (200次调整)', ylabel='元/吨', rotation=15,
                              data=[df_long['gasoline'], df_long['diesel']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/oil.png"
        self.plotter.save(fig, path)
        return path
