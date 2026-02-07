
import akshare as ak
import pandas as pd
from .base import BaseIndicator

class CommodityIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        """Fetch Gold Data (Max History)"""
        try:
            # COMEX Gold
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
        
        # Data
        # 20 Years approx 250*20 = 5000
        df_long = df.iloc[-5000:].copy() 
        df_short = df.iloc[-250:].copy() # 1 Year
        
        # --- Top: Short (1Y) ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['close'], label='COMEX黄金 (1Y)', color='gold', linewidth=2)
        self.plotter.draw_current_line(df_short['close'].iloc[-1], ax_top, 'gold')
        
        self.plotter.fmt_single(fig, ax_top, title='大宗商品-黄金 (近期)', ylabel='美元/盎司', rotation=45)
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: Long (20Y) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['close'], color='goldenrod', linewidth=1)
        ax_bot.fill_between(df_long['date'], df_long['close'], color='goldenrod', alpha=0.1)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年)', ylabel='美元', rotation=45)
        self.plotter.set_no_margins(ax_bot)
        
        # Save
        path = "output/finance/commodity.png"
        self.plotter.save(fig, path)
        return path
