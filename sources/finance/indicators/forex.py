import akshare as ak
import pandas as pd
from .base import BaseIndicator

class ForexIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.currency_boc_safe()
            df = df[['日期', '美元', '欧元', '日元', '英镑']]
            df = df.rename(columns={'日期': 'date', '美元': 'USD', '欧元': 'EUR', '日元': 'JPY', '英镑': 'GBP'})
            df['date'] = pd.to_datetime(df['date'])
            df.sort_values('date', inplace=True)
            return df
        except Exception as e:
            self.logger.error(f"Forex Fetch Error: {e}")
            raise e

    def plot_dual(self, ax, df):
        ax_r = ax.twinx()
        usd = df['USD'] / 100
        eur = df['EUR'] / 100
        gbp = df['GBP'] / 100
        jpy = df['JPY'] 
        
        # Color Palette - Global Forex Theme
        c_usd = '#e74c3c'  # Crimson (基准货币)
        c_eur = '#3498db'  # Dodger Blue (主要对手)
        c_gbp = '#8e44ad'  # Wisteria (传统货币)
        c_jpy = '#95a5a6'  # Concrete (避险/套息 - 虚线)
        
        ax.plot(df['date'], usd, color=c_usd, linewidth=2.5, label='美元 (USD)', zorder=3)
        ax.plot(df['date'], eur, color=c_eur, linewidth=2, label='欧元 (EUR)', zorder=2)
        ax.plot(df['date'], gbp, color=c_gbp, linewidth=1.5, label='英镑 (GBP)', alpha=0.8, zorder=2)
        ax_r.plot(df['date'], jpy, color=c_jpy, linewidth=1.5, linestyle=':', label='日元 (JPY/100)')
        
        # Merge legends
        h1, l1 = ax.get_legend_handles_labels()
        h2, l2 = ax_r.get_legend_handles_labels()
        ax.legend(h1+h2, l1+l2, loc='upper left', frameon=True, framealpha=0.9, fontsize=8)
        
        return ax, ax_r

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show ~20 years
        df_long = df.iloc[-5000:].copy() 
        
        # --- Top ---
        ax_top, ax_top_r = self.plot_dual(axes[0], df_short)
        
        # Draw current line for USD (Benchmark)
        self.plotter.draw_current_line((df_short['USD']/100).iloc[-1], ax_top, '#e74c3c')
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, title='外汇市场-汇率中间价 (近期13月)', 
                             ylabel_left='CNY', ylabel_right='JPY(100)',
                             data_left=[df_short['USD']/100, df_short['EUR']/100, df_short['GBP']/100],
                             data_right=df_short['JPY'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom ---
        ax_bot, ax_bot_r = self.plot_dual(axes[1], df_long)
        ax_bot.legend().set_visible(False) # Hide legend on bottom chart
        
        # Gradient fill for USD
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['USD']/100, color='#e74c3c', alpha_top=0.2)
        
        self.plotter.fmt_twinx(fig, ax_bot, ax_bot_r, title='历史走势 (20年全景)', 
                             ylabel_left='', ylabel_right='',
                             data_left=[df_long['USD']/100, df_long['EUR']/100, df_long['GBP']/100],
                             data_right=df_long['JPY'])
        self.plotter.set_no_margins(ax_bot)

        path = "output/finance/forex.png"
        self.plotter.save(fig, path)
        return path
