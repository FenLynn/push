import akshare as ak
import pandas as pd
from .base import BaseIndicator

class NEVSaleIndicator(BaseIndicator):
    """新能源车销量 (New Energy Vehicle)"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.car_market_total_cpca()
            # 月份, 2024年, 2025年, ...
            # Melt to long format
            df_melted = df.melt(id_vars=['月份'], var_name='year', value_name='sales')
            df_melted['date'] = pd.to_datetime(df_melted['year'] + '-' + df_melted['月份'], format='%Y年-%m月')
            df_melted['sales'] = pd.to_numeric(df_melted['sales'], errors='coerce')
            return df_melted[['date', 'sales']].sort_values('date').dropna()
        except Exception as e:
            self.logger.error(f"NEV Sale Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: last 5 years (60 months)
        df_long = df.iloc[-60:].copy() 
        
        # Color Palette - Energy Green Theme
        c_bar = '#16a085'  # Green Sea (销量柱状)
        c_line = '#2ecc71' # Emerald (趋势高亮)
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        # Bar + Line combo
        ax_top.bar(df_short['date'], df_short['sales'], color=c_bar, alpha=0.6, width=20, label='月度销量(柱)', zorder=1)
        ax_top.plot(df_short['date'], df_short['sales'], 'o-', markersize=6, color=c_line, linewidth=2.5, label='趋势(线)', zorder=2)
        
        # Data Labels (Optimized)
        for x, y in zip(df_short['date'], df_short['sales']):
            ax_top.text(x, y + (y * 0.05), f'{y:.1f}', ha='center', va='bottom', fontsize=9, fontweight='bold', color=c_bar)

        # Explicit legend
        ax_top.legend(loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='行业数据-新能源车销量 (近期13月)', 
                               ylabel='万辆', rotation=15, 
                               data=df_short['sales'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom (History) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['sales'], color=c_line, linewidth=2, label='历史趋势')
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['sales'], color=c_line, alpha_top=0.3)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (5年全景)', ylabel='万辆', rotation=15, 
                               data=df_long['sales'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/nev_sale.png"
        self.plotter.save(fig, path)
        return path
