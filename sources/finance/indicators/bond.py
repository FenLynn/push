import akshare as ak
import pandas as pd
from .base import BaseIndicator

class BondIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.bond_zh_us_rate()
            df = df.rename(columns={
                '日期': 'date',
                '中国国债收益率10年': 'y10',
                '中国国债收益率2年': 'y2'
            })
            df['date'] = pd.to_datetime(df['date'])
            df['y10'] = pd.to_numeric(df['y10'], errors='coerce')
            df['y2'] = pd.to_numeric(df['y2'], errors='coerce')
            df['spread'] = (df['y10'] - df['y2']) * 100 # BP
            return df.dropna(subset=['y10', 'y2']).sort_values('date')
        except Exception as e:
            self.logger.error(f"Bond Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        df_long = df.iloc[-5000:].copy() 
        
        # Color Palette - Premium Bond Theme
        c_10y = '#e74c3c'  # Crimson (长端无风险利率)
        c_2y = '#3498db'   # Dodger Blue (短端无风险利率)
        c_spread = '#95a5a6'  # Silver Gray (宏观预期指标)
        
        # --- Top ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['y10'], color=c_10y, linewidth=3.5, label='国债10Y', zorder=3)
        ax_top.plot(df_short['date'], df_short['y2'], color=c_2y, linewidth=2.5, label='国债2Y', zorder=2)
        
        # Draw current value line for 10Y
        self.plotter.draw_current_line(df_short['y10'].iloc[-1], ax_top, c_10y)
        
        # Twin axis for spread
        ax_top_r = ax_top.twinx()
        ax_top_r.fill_between(df_short['date'], df_short['spread'], color=c_spread, alpha=0.15, label='期限利差(BP)')
        ax_top_r.plot(df_short['date'], df_short['spread'], color=c_spread, linewidth=1.5, linestyle='--', alpha=0.7)
        
        # Merge legends
        h1, l1 = ax_top.get_legend_handles_labels()
        h2, l2 = ax_top_r.get_legend_handles_labels()
        ax_top.legend(h1+h2, l1+l2, loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, title='债券市场-国债收益率 (近期13月)', 
                             ylabel_left='收益率(%)', ylabel_right='利差(BP)',
                             data_left=[df_short['y10'], df_short['y2']], data_right=df_short['spread'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['y10'], color=c_10y, linewidth=1.8, alpha=0.9, label='10Y')
        ax_bot.plot(df_long['date'], df_long['y2'], color=c_2y, linewidth=1.2, alpha=0.7, label='2Y')
        
        # Gradient fill for 10Y (risk-free benchmark)
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['y10'], color=c_10y, alpha_top=0.25)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年全景)', 
                               ylabel='收益率(%)', rotation=15, 
                               data=[df_long['y10'], df_long['y2']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/bond.png"
        self.plotter.save(fig, path)
        return path
