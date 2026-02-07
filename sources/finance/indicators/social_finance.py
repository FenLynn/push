import akshare as ak
import pandas as pd
from .base import BaseIndicator

class SocialFinanceIndicator(BaseIndicator):
    """社会融资规模增量"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_shrzgm()
            # Standardize
            df['date'] = pd.to_datetime(df['月份'], format='%Y%m')
            df['value'] = df['社会融资规模增量']
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Use 3:1 ratio layout
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Data windows - monthly data: 12 months = 1 year, 240 months = 20 years
        df_short = df.iloc[-12:].copy()   # Recent 1 year
        df_long = df.iloc[-240:].copy()   # History 20 years (or all available)
        
        # Color
        color = '#E74C3C'  # Red
        
        # --- Top: Recent (1 Year) with markers ---
        ax_top = axes[0]
        ax_top.bar(df_short['date'], df_short['value'], 
                  color=color, alpha=0.7, width=20, label='社融增量')
        ax_top.plot(df_short['date'], df_short['value'], 
                   'o-', markersize=5, color=color, linewidth=2)
        
        # Current value line
        try:
            curr = df_short.iloc[-1]['value']
            self.plotter.draw_current_line(curr, ax_top, color)
        except: pass
        
        # Format top
        self.plotter.fmt_single(fig, ax_top, 
                              title='宏观数据-社会融资规模增量 (近期)',
                              ylabel='社融增量(亿元)', 
                              sci_on=True, rotation=15)
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History (20 Years) ---
        ax_bot = axes[1]
        ax_bot.fill_between(df_long['date'], df_long['value'], 
                           color=color, alpha=0.3)
        ax_bot.plot(df_long['date'], df_long['value'], 
                   color=color, linewidth=1.5, label='社融增量')
        
        # Format bottom with internal title
        self.plotter.fmt_single(fig, ax_bot, 
                              title='历史走势 (20年)',
                              ylabel='社融增量(亿元)', 
                              sci_on=True, rotation=15)
        self.plotter.set_no_margins(ax_bot)
        
        # Save
        path = "output/finance/shrzgm.png"
        self.plotter.save(fig, path)
        return path
