
import akshare as ak
import pandas as pd
from .base import BaseIndicator

class ForexIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        """Fetch Forex Rates"""
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

    def plot_dual(self, ax, df, title):
        ax_r = ax.twinx()
        
        usd = df['USD'] / 100
        eur = df['EUR'] / 100
        gbp = df['GBP'] / 100
        jpy = df['JPY'] 
        
        ax.plot(df['date'], usd, color='red', linewidth=1.5, label='美元')
        ax.plot(df['date'], eur, color='blue', linewidth=1.5, label='欧元')
        ax.plot(df['date'], gbp, color='purple', linewidth=1.5, label='英镑')
        
        ax_r.plot(df['date'], jpy, color='orange', linewidth=1.5, linestyle='--', label='日元(100)')
        
        return ax, ax_r

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df_long = df.iloc[-5000:].copy()
        df_short = df.iloc[-250:].copy()
        
        # --- Top: Recent ---
        ax_top, ax_top_r = self.plot_dual(axes[0], df_short, "近期")
        self.plotter.draw_current_line((df_short['USD']/100).iloc[-1], ax_top, 'red')
        
        # Legend
        h1, l1 = ax_top.get_legend_handles_labels()
        h2, l2 = ax_top_r.get_legend_handles_labels()
        ax_top.legend(h1+h2, l1+l2, loc='upper left', frameon=True, ncol=4)
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, title='外汇市场-汇率中间价 (近期)', ylabel_left='CNY', ylabel_right='JPY(100)')
        self.plotter.set_no_margins(ax_top)
        self.plotter.set_no_margins(ax_top_r)
        
        # --- Bottom: Long ---
        ax_bot, ax_bot_r = self.plot_dual(axes[1], df_long, "历史")
        # No Legend for small chart to save space
        
        self.plotter.fmt_twinx(fig, ax_bot, ax_bot_r, title='历史走势', ylabel_left='', ylabel_right='')
        self.plotter.set_no_margins(ax_bot)
        self.plotter.set_no_margins(ax_bot_r)

        path = "output/finance/forex.png"
        self.plotter.save(fig, path)
        return path
