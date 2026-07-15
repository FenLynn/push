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
        
        # Calculate Synthetic CPI Index (Base 100 at start of 20 years)
        # Using MoM to reconstruct the price level curve
        # Index_t = Index_{t-1} * (1 + MoM_t/100)
        df = df.sort_values('date').reset_index(drop=True)
        # Start from 100
        df['cpi_index'] = 100.0
        for i in range(1, len(df)):
            df.loc[i, 'cpi_index'] = df.loc[i-1, 'cpi_index'] * (1 + df.loc[i, 'cpi_m']/100)

        # 1. Data Slicing
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        df_long = df.iloc[-240:].copy() 
        
        # Color Palette - Premium & Distinct
        c_infl_line = '#c0392b'  # Deep Red (YoY Line)
        c_infl_bar = '#e74c3c'   # Bright Red (YoY Bar)
        c_index_line = '#2c3e50' # Midnight Blue (Index)
        c_index_fill = '#34495e' # Wet Asphalt (Index Fill)
        
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

        # --- Bottom Chart: Historical Context (Price Level + Inflation) ---
        ax_bot = axes[1]
        
        # Left Axis: CPI Index (Synthetic Price Level)
        # Using Area Chart for Index
        ax_bot.plot(df_long['date'], df_long['cpi_index'], color=c_index_line, linewidth=1.5, label='价格水平(虚拟指数)')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['cpi_index'], color=c_index_fill, alpha_top=0.2)
        
        # Right Axis: CPI YoY (Bars)
        ax_bot_r = ax_bot.twinx()
        # Use bars for YoY, distinct color
        ax_bot_r.bar(df_long['date'], df_long['cpi_y'], width=20, alpha=0.4, color=c_infl_bar, label='CPI同比涨幅')
        ax_bot_r.axhline(y=0, color='#95a5a6', linestyle='--', linewidth=0.8, alpha=0.5)
        
        # Explicit Legend Fix: Combine handles
        h1, l1 = ax_bot.get_legend_handles_labels()
        h2, l2 = ax_bot_r.get_legend_handles_labels()
        ax_bot.legend(h1+h2, l1+l2, loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_twinx(fig, ax_bot, ax_bot_r, 
                               title='历史走势 (20年: 价格水平 vs 通胀率)', 
                               ylabel_left='价格指数', 
                               ylabel_right='通胀率(%)',
                               rotation=15, 
                               data_left=df_long['cpi_index'],
                               data_right=df_long['cpi_y'])
        self.plotter.set_no_margins(ax_bot)
        
        # Final Polish
        path = "output/finance/cpi.png"
        self.plotter.save(fig, path)
        return path
