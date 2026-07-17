import akshare as ak
import pandas as pd
from .base import BaseIndicator

class CPIIndicator(BaseIndicator):
    @staticmethod
    def _normalize_nbs_frame(frame: pd.DataFrame) -> pd.DataFrame:
        required = {'月份', '全国-同比增长', '全国-环比增长'}
        missing = required.difference(frame.columns)
        if missing:
            raise RuntimeError(f"CPI upstream columns changed: {sorted(missing)}")

        month_parts = frame['月份'].astype(str).str.extract(r'(?P<year>\d{4})年(?P<month>\d{1,2})月份?')
        dates = pd.to_datetime(
            month_parts['year'] + '-' + month_parts['month'].str.zfill(2) + '-01',
            errors='coerce',
        )
        normalized = pd.DataFrame({
            'date': dates,
            'cpi_y': pd.to_numeric(frame['全国-同比增长'], errors='coerce'),
            'cpi_m': pd.to_numeric(frame['全国-环比增长'], errors='coerce'),
        })
        return normalized.dropna(subset=['date', 'cpi_y']).drop_duplicates('date').sort_values('date')

    def fetch_data(self) -> pd.DataFrame:
        try:
            # This dataset is sourced from the National Bureau of Statistics
            # and uses observation months. The legacy yearly/monthly helpers
            # expose release-calendar dates and stopped updating in 2025.
            frame = self._normalize_nbs_frame(ak.macro_china_cpi())
        except Exception as exc:
            self.logger.error("CPI Fetch Error: %s", exc)
            raise

        if frame.empty:
            raise RuntimeError("CPI upstream returned no observations; synthetic fallback is disabled")
        return frame

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        df = df.sort_values('date').reset_index(drop=True)

        # 1. Data Slicing
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        df_long = df.iloc[-240:].copy() 
        
        # Color Palette - Premium & Distinct
        c_infl_line = '#c0392b'  # Deep Red (YoY Line)
        c_infl_bar = '#e74c3c'   # Bright Red (YoY Bar)
        c_mom = '#3976a8'
        
        # --- Top Chart: Recent Trends (YoY Inflation) ---
        ax_top = axes[0]
        # Main Line: CPI YoY
        # Add distinct markers and shadow effect
        ax_top.plot(df_short['date'], df_short['cpi_y'], 'D-', 
                   color=c_infl_line, linewidth=2.5, markersize=8, 
                   markeredgecolor='white', markeredgewidth=1.5,
                   label='CPI同比')
        
        # Current Value Annotation
        self.plotter.draw_current_line(df_short.iloc[-1]['cpi_y'], ax_top, c_infl_line)
        
        # Zero Line
        ax_top.axhline(y=0, color='#95a5a6', linestyle='--', linewidth=1, alpha=0.8)

        # Standard Formatting
        self.plotter.fmt_single(fig, ax_top, 
                             title='CPI居民消费价格指数 (近期13月)', 
                             ylabel='同比(%)',
                             rotation=15, 
                             data=df_short['cpi_y'])
        self.plotter.set_no_margins(ax_top)

        # --- Bottom Chart: original long-term YoY with MoM bars. Do not
        # reconstruct an unlabeled synthetic price-level index. ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['cpi_y'], color=c_infl_line, linewidth=1.5, label='CPI同比')
        ax_bot.bar(df_long['date'], df_long['cpi_m'], width=20, alpha=0.24, color=c_mom, label='CPI环比')
        ax_bot.axhline(y=0, color='#95a5a6', linestyle='--', linewidth=0.8, alpha=0.6)
        self.plotter.fmt_single(fig, ax_bot, title='CPI同比与环比（20年）',
                               ylabel='%', rotation=15,
                               data=[df_long['cpi_y'], df_long['cpi_m']])
        self.plotter.set_no_margins(ax_bot)
        
        # Final Polish
        path = "output/finance/cpi.png"
        self.plotter.save(fig, path)
        return path
