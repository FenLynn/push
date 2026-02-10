import akshare as ak
import pandas as pd
from .base import BaseIndicator

class CommodityIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.futures_foreign_hist(symbol="GC") 
            df = df.rename(columns={'date': 'date', 'close': 'close'})
            df['date'] = pd.to_datetime(df['date'])
            df.sort_values('date', inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Commodity Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show ~20 years
        df_long = df.iloc[-5000:].copy() 
        
        # Color Palette - Premium Gold
        c_gold = '#f39c12'  # Orange/Gold (避险资产)
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['close'], color=c_gold, linewidth=3, label='COMEX黄金')
        self.plotter.draw_current_line(df_short['close'].iloc[-1], ax_top, c_gold)
        
        # Explicit legend
        ax_top.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='大宗商品-黄金 (近期13月)', 
                               ylabel='美元/盎司', rotation=15, data=df_short['close'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['close'], color=c_gold, linewidth=1.5, alpha=0.9)
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['close'], color=c_gold, alpha_top=0.25)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年全景)', 
                               ylabel='美元/盎司', rotation=15, data=df_long['close'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/commodity.png"
        self.plotter.save(fig, path)
        return path
