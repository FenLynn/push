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
        
        c1 = '#E74C3C' # 10Y - Red
        c2 = '#273c75' # 2Y - Blue
        c3 = '#7f8c8d' # Spread - Gray
        
        # --- Top ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['y10'], color=c1, linewidth=3, label='国债10Y')
        ax_top.plot(df_short['date'], df_short['y2'], color=c2, linewidth=2.5, label='国债2Y')
        
        ax_top_r = ax_top.twinx()
        ax_top_r.fill_between(df_short['date'], df_short['spread'], color=c3, alpha=0.1, label='期限利差(BP)')
        ax_top_r.plot(df_short['date'], df_short['spread'], color=c3, linewidth=1, linestyle='--')
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, title='债券市场-国债收益率 (近期13月)', 
                             ylabel_left='收益率(%)', ylabel_right='利差(BP)',
                             data_left=[df_short['y10'], df_short['y2']], data_right=df_short['spread'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['y10'], color=c1, linewidth=1.5, label='10Y')
        ax_bot.plot(df_long['date'], df_long['y2'], color=c2, linewidth=1, alpha=0.6)
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['y10'], color=c1, alpha_top=0.2)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势', ylabel='收益率(%)', rotation=15, 
                               data=[df_long['y10'], df_long['y2']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/bond.png"
        self.plotter.save(fig, path)
        return path
