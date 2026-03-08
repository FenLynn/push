import akshare as ak
import pandas as pd
from .base import BaseIndicator
import numpy as np

class SocialFinanceIndicator(BaseIndicator):
    """社会融资规模增量 (10年期平滑版)"""
    def fetch_data(self) -> pd.DataFrame:
        import time
        df_src = pd.DataFrame()
        for attempt in range(3):
            try:
                df_src = ak.macro_china_shrzgm()
                df_src['date'] = pd.to_datetime(df_src['月份'], format='%Y%m')
                df_src['value'] = df_src['社会融资规模增量'].astype(float)
                break
            except Exception as e:
                if attempt == 2:
                    self.logger.warning(f"Social Finance Fetch failed, using reconstruction: {e}")
                time.sleep(1)

        # 10年期补全
        dr = pd.date_range(end=pd.Timestamp.now().normalize(), periods=3650, freq='D')
        df_final = pd.DataFrame({'date': dr})
        
        if not df_src.empty:
            df_final = pd.merge(df_final, df_src[['date', 'value']], on='date', how='left')
        else:
            self.logger.warning("Social Finance: data unavailable, skipping.")
            return None
            
        # 线性插值
        df_final['value'] = df_final['value'].interpolate(method='linear').ffill().bfill()
        
        return df_final.sort_values('date')

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # Calculate Synthetic Stock (Cumulative Increment)
        # Assuming a base stock at start of data to make it look realistic (though trends matter more)
        # Let's say approx 100 Trillion (1000000 亿元) base? 
        # Actually just cumsum from 0 is fine for trend analysis, or use the mean fitting base.
        # But to be safe and avoid negative logic if any, just cumsum + large base.
        # The fetch_data already handles some fitting if empty.
        # Let's just use cumsum on the sorted data.
        df = df.sort_values('date').reset_index(drop=True)
        # Approximate base: 200 Trillion CNY (2024 data is ~400T stock). 
        # 10 years ago maybe 100T? Let's verify. 2017 stock was ~150T.
        # 2014 ~100T. So let's start with 100,000 (10000000000 is 100亿? No, unit is 亿元).
        # 1 Trillion = 10000 亿元. 100T = 1,000,000 亿元.
        base_stock = 1000000.0 
        df['stock_proxy'] = df['value'].cumsum() + base_stock

        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # Color Palette - Premium & Distinct
        c_inc_bar = '#2980b9'    # Belize Hole (Blue) for Increment
        c_inc_line = '#3498db'   # Peter River (Lighter Blue) for Line
        c_stock_line = '#8e44ad' # Wisteria (Purple) for Stock
        c_stock_fill = '#9b59b6' # Amethyst (Lighter Purple)
        
        # --- Top Chart: Recent Trends (Increment Flow) ---
        ax_top = axes[0]
        # Bar Chart for Flow
        ax_top.bar(df_short['date'], df_short['value'], color=c_inc_bar, alpha=0.6, width=20, label='社融增量')
        # Line overlay with shadow effect
        ax_top.plot(df_short['date'], df_short['value'], 'o-', 
                   color=c_inc_line, linewidth=2, markersize=6, 
                   markeredgecolor='white', markeredgewidth=1)
        
        self.plotter.draw_current_line(df_short.iloc[-1]['value'], ax_top, c_inc_line)

        # Standard Formatting
        self.plotter.fmt_single(fig, ax_top, 
                             title='社会融资规模增量 (近期13月资金流量)', 
                             ylabel='增量(亿元)', 
                             sci_on=True,
                             rotation=15, 
                             data=df_short['value'])
        self.plotter.set_no_margins(ax_top)
        ax_top.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9)
        
        # --- Bottom Chart: Historical Context (Stock vs Flow) ---
        ax_bot = axes[1]
        
        # Left Axis: Stock Proxy (Line)
        ax_bot.plot(df['date'], df['stock_proxy'], color=c_stock_line, linewidth=2, label='社融存量(拟合)')
        # Smoother gradient
        self.plotter.fill_gradient(ax_bot, df['date'], df['stock_proxy'], color=c_stock_fill, alpha_top=0.3)
        
        # Right Axis: Increment (Bars)
        ax_bot_r = ax_bot.twinx()
        ax_bot_r.bar(df['date'], df['value'], width=20, alpha=0.3, color=c_inc_bar, label='社融增量')
        
        # Explicit Legend Fix
        h1, l1 = ax_bot.get_legend_handles_labels()
        h2, l2 = ax_bot_r.get_legend_handles_labels()
        ax_bot.legend(h1+h2, l1+l2, loc='upper left', frameon=True, framealpha=0.9, fontsize=9)

        self.plotter.fmt_twinx(fig, ax_bot, ax_bot_r, 
                               title='历史走势 (10年: 资金存量水位 vs 增量)', 
                               ylabel_left='存量(拟合)', 
                               ylabel_right='增量(亿元)',
                               rotation=15, 
                               data_left=df['stock_proxy'],
                               data_right=df['value'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/socialfinance.png"
        self.plotter.save(fig, path)
        return path
