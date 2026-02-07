import akshare as ak
import pandas as pd
from .base import BaseIndicator

class PigIndicator(BaseIndicator):
    """生猪价格指数"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.index_hog_spot_price()
            df = df.rename(columns={'日期': 'date', '指数': 'index'})
            df['date'] = pd.to_datetime(df['date'])
            df['index'] = pd.to_numeric(df['index'], errors='coerce')
            return df.dropna(subset=['index']).sort_values('date')
        except Exception as e:
            self.logger.error(f"Pig Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show ~10 years (Daily data, so ~2500 rows)
        df_long = df.iloc[-2500:].copy() 
        
        color = '#273c75' # Energy Blue
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['index'], color=color, linewidth=2.5, label='生猪价格指数')
        self.plotter.draw_current_line(df_short['index'].iloc[-1], ax_top, color)
        
        self.plotter.fmt_single(fig, ax_top, title='行业数据-生猪价格指数 (近期13月)', ylabel='指数', rotation=15, data=df_short['index'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['index'], color=color, linewidth=1.5)
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['index'], color=color)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势', ylabel='指数', rotation=15, data=df_long['index'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/pig.png"
        self.plotter.save(fig, path)
        return path
