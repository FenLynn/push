
import akshare as ak
import pandas as pd
from .base import BaseIndicator

class SOXIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        """Fetch SOX Data"""
        try:
            df = ak.index_us_stock_sina(symbol=".SOX")
            df['date'] = pd.to_datetime(df['date'])
            df.sort_values('date', inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"SOX Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df_long = df.iloc[-5000:].copy()
        df_short = df.iloc[-250:].copy()
        
        # Top: Recent
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['close'], color='mediumpurple', linewidth=2, label='SOX')
        self.plotter.draw_current_line(df_short['close'].iloc[-1], ax_top, 'mediumpurple')
        
        self.plotter.fmt_single(fig, ax_top, title='全球科技-费城半导体 (近期)', ylabel='点位', rotation=45)
        self.plotter.set_no_margins(ax_top)
        
        # Bottom: Long
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['close'], color='mediumpurple', linewidth=1)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势', ylabel='点位', rotation=45)
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/sox.png"
        self.plotter.save(fig, path)
        return path
