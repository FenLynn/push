
import akshare as ak
import pandas as pd
from .base import BaseIndicator

class BondIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        """Fetch US/CN Bond Yields (10Y, 2Y as Short)"""
        try:
            df = ak.bond_zh_us_rate()
            df['date'] = pd.to_datetime(df['日期'])
            df.sort_values('date', inplace=True)
            # Fix breakpoints: Forward Fill
            df = df.fillna(method='ffill')
            return df
        except Exception as e:
            self.logger.error(f"Bond Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Layout: Top (Recent, 3/4), Bottom (Long, 1/4)
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # Data
        df['date'] = pd.to_datetime(df['date'])
        df_long = df.iloc[-5000:].copy() # Max 20 Years
        df_short = df.iloc[-250:].copy()
        
        # --- Top: Recent (Dual Axis) ---
        ax_top = axes[0]
        ax_top_r = ax_top.twinx()
        
        # Left: Yields
        us_10 = df_short['美国国债收益率10年']
        us_2  = df_short['美国国债收益率2年']
        cn_10 = df_short['中国国债收益率10年']
        cn_2  = df_short['中国国债收益率2年']
        spread = us_10 - cn_10
        
        ax_top.plot(df_short['date'], us_10, color='firebrick', linewidth=2, label='美债10Y')
        ax_top.plot(df_short['date'], us_2, color='lightcoral', linewidth=1.5, linestyle=':', label='美债2Y')
        ax_top.plot(df_short['date'], cn_10, color='dodgerblue', linewidth=2, label='中债10Y')
        ax_top.plot(df_short['date'], cn_2, color='skyblue', linewidth=1.5, linestyle=':', label='中债2Y')
        
        # Right: Spread
        ax_top_r.bar(df_short['date'], spread, color='gray', alpha=0.2, label='中美利差(BP)', width=1.0)
        
        # Current
        self.plotter.draw_current_line(us_10.iloc[-1], ax_top, 'firebrick')
        self.plotter.draw_current_line(cn_10.iloc[-1], ax_top, 'dodgerblue')

        # Legend
        h1, l1 = ax_top.get_legend_handles_labels()
        h2, l2 = ax_top_r.get_legend_handles_labels()
        ax_top.legend(h1+h2, l1+l2, loc='upper left', frameon=True, ncol=3)

        # Format Top
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, title='宏观-中美利差 & 国债收益率 (近期)', ylabel_left='收益率(%)', ylabel_right='利差(%)')
        self.plotter.set_no_margins(ax_top)
        self.plotter.set_no_margins(ax_top_r)

        # --- Bottom: Long (Yields only) ---
        ax_bot = axes[1]
        
        ax_bot.plot(df_long['date'], df_long['美国国债收益率10年'], color='firebrick', linewidth=1, label='美10Y')
        ax_bot.plot(df_long['date'], df_long['中国国债收益率10年'], color='dodgerblue', linewidth=1, label='中10Y')
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (全部)', ylabel='收益率(%)', rotation=45)
        self.plotter.set_no_margins(ax_bot)

        # Save
        path = "output/finance/bond.png"
        self.plotter.save(fig, path)
        return path
