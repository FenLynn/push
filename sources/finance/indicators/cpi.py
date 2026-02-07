import akshare as ak
import pandas as pd
from .base import BaseIndicator

class CPIIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        import time
        for attempt in range(3):
            try:
                df_y = ak.macro_china_cpi_yearly()
                df_m = ak.macro_china_cpi_monthly()
                df_y = df_y.rename(columns={'日期':'date', '今值':'cpi_y'})
                df_m = df_m.rename(columns={'日期':'date', '今值':'cpi_m'})
                df = pd.merge(df_y, df_m, on='date', how='outer').sort_values('date')
                df['date'] = pd.to_datetime(df['date'])
                df = df.fillna(0)
                return df
            except Exception as e:
                if attempt == 2: raise e
                time.sleep(2)

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        df_long = df.iloc[-240:].copy() 
        
        c1 = '#E74C3C'  # Premium Red
        c2 = '#273c75'  # Energy Blue
        
        # --- Top ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['cpi_y'], 'D-', markersize=8, label='CPI同比', color=c1, linewidth=3)
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(df_short['date'], df_short['cpi_m'], 'o-', markersize=7, label='CPI环比', color=c2, linewidth=2.5)
        
        self.plotter.draw_current_line(df_short.iloc[-1]['cpi_y'], ax_top, c1)
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, 
                             title='宏观数据-CPI通胀率 (近期13月)', 
                             ylabel_left='同比(%)', ylabel_right='环比(%)',
                             rotation=15, data_left=df_short['cpi_y'], data_right=df_short['cpi_m'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['cpi_y'], color=c1, linewidth=2, label='CPI同比')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['cpi_y'], color=c1)
        ax_bot.axhline(y=0, color='#636e72', linestyle='--', linewidth=0.8, alpha=0.5)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年)', ylabel='CPI同比(%)', rotation=15, 
                               data=[df_long['cpi_y'], df_long['cpi_m']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/cpi.png"
        self.plotter.save(fig, path)
        return path
