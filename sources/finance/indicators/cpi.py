import akshare as ak
import pandas as pd
from .base import BaseIndicator

class CPIIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        """Fetch CPI Data (Yearly + Monthly)"""
        import time
        
        # Retry logic for network issues
        for attempt in range(3):
            try:
                df_y = ak.macro_china_cpi_yearly()
                df_m = ak.macro_china_cpi_monthly()
                
                df_y = df_y.rename(columns={'日期':'date', '今值':'cpi_y'})
                df_m = df_m.rename(columns={'日期':'date', '今值':'cpi_m'})
                
                # Merge
                df = pd.merge(df_y, df_m, on='date', how='outer').sort_values('date')
                df['date'] = pd.to_datetime(df['date'])
                df = df.fillna(0)
                return df
                
            except Exception as e:
                if attempt == 2:
                    self.logger.error(f"CPI Fetch Failed After 3 Attempts: {e}")
                    raise e
                self.logger.warning(f"CPI Fetch Attempt {attempt+1} failed, retrying...")
                time.sleep(2)

    def plot(self, df: pd.DataFrame) -> str:
        # Use 3:1 ratio layout
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Data windows - monthly data, so 12 months = 1 year, 240 months = 20 years
        df_short = df.iloc[-12:].copy()   # Recent 1 year
        df_long = df.iloc[-240:].copy()   # History 20 years (or all available)
        
        # Colors
        c1 = '#E74C3C'  # CPI同比 (Yearly) - Red
        c2 = '#3498DB'  # CPI环比 (Monthly) - Blue
        
        # --- Top: Recent (1 Year) - Dual Y-axis ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['cpi_y'], 'D-', markersize=4, 
                   label='CPI同比', color=c1, linewidth=2)
        
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(df_short['date'], df_short['cpi_m'], 'o-', markersize=4, 
                     label='CPI环比', color=c2, linewidth=2)
        
        # Current value lines
        try:
            curr_y = df_short.iloc[-1]['cpi_y']
            curr_m = df_short.iloc[-1]['cpi_m']
            self.plotter.draw_current_line(curr_y, ax_top, c1)
            self.plotter.draw_current_line(curr_m, ax_top_r, c2)
        except: pass
        
        # Format top
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r, 
                             title='宏观数据-CPI增长率 (近期)', 
                             ylabel_left='CPI同比(%)', 
                             ylabel_right='CPI环比(%)',
                             rotation=15)
        self.plotter.set_no_margins(ax_top)
        self.plotter.set_no_margins(ax_top_r)
        
        # --- Bottom: History (20 Years) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['cpi_y'], label='CPI同比', 
                   color=c1, linewidth=1.5)
        ax_bot.plot(df_long['date'], df_long['cpi_m'], label='CPI环比', 
                   color=c2, linewidth=1.5)
        
        # Format bottom with internal title
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年)', 
                              ylabel='增长率(%)', rotation=15)
        self.plotter.set_no_margins(ax_bot)
        
        # Save
        path = f"output/finance/cpi.png"
        self.plotter.save(fig, path)
        return path
