import akshare as ak
import pandas as pd
from .base import BaseIndicator

class RealEstateIndicator(BaseIndicator):
    """国房景气指数"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_real_estate()
            # 日期, 最新值, 涨跌幅, ...
            df = df.rename(columns={
                '日期': 'date',
                '最新值': 'value'
            })
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df[['date', 'value']].sort_values('date')
        except Exception as e:
            self.logger.error(f"Real Estate Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: last 20 years (240 months)
        df_long = df.iloc[-240:].copy() 
        
        # Color Palette - Construction Orange Theme
        c_index = '#d35400'    # Pumpkin (警示与行业色)
        c_baseline = '#7f8c8d' # Asbestos (中性线基准)
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['value'], color=c_index, linewidth=3.5, marker='o', markersize=6, label='国房景气指数', zorder=3)
        
        # 100 baseline (neutral) - Strengthened
        ax_top.axhline(y=100, color=c_baseline, linestyle='--', alpha=0.8, linewidth=1.5, label='中性线(100)', zorder=2)
        
        # Draw current value line
        self.plotter.draw_current_line(df_short['value'].iloc[-1], ax_top, c_index)
        
        # Explicit legend
        ax_top.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='行业数据-国房景气指数 (近期13月)', 
                               ylabel='指数', rotation=15, 
                               data=df_short['value'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom (History) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['value'], color=c_index, linewidth=1.8, label='历史走势')
        ax_bot.axhline(y=100, color='#bdc3c7', linestyle='--', alpha=0.5, linewidth=1)
        
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['value'], color=c_index, alpha_top=0.25)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年全景)', ylabel='指数', rotation=15, 
                               data=df_long['value'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/real_estate.png"
        self.plotter.save(fig, path)
        return path
