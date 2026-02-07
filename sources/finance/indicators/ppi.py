import akshare as ak
import pandas as pd
from .base import BaseIndicator

class PPIIndicator(BaseIndicator):
    """PPI 工业生产者价格指数"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            # NBS PPI Data Basis:
            # '当月' refers to the Price Index relative to the same month last year (Last Year = 100).
            # '当月同比增长' is simply (Index - 100).
            # These are mathematically redundant. Plotting both is unnecessary.
            df = ak.macro_china_ppi()
            
            cols = df.columns.tolist()
            date_col = next((c for c in cols if '月份' in c or '日期' in c), cols[0])
            ppi_col = next((c for c in cols if '当月' in c and '同比' not in c), cols[1])
            growth_col = next((c for c in cols if '同比增长' in c), None)
            
            df = df.rename(columns={
                date_col: 'date',
                ppi_col: 'ppi_index_yoy', # This is Index (Last Year=100)
                growth_col: 'ppi_growth'   # This is Growth Rate (%)
            })
            
            # Date Parsing: "2024年01月份" -> "2024-01-01"
            df['date'] = df['date'].str.replace('月份', '').str.replace('年', '-').str.replace('月', '-')
            df['date'] = pd.to_datetime(df['date'])
            
            df['ppi_index_yoy'] = pd.to_numeric(df['ppi_index_yoy'], errors='coerce')
            df['ppi_growth'] = pd.to_numeric(df['ppi_growth'], errors='coerce')
            
            return df.dropna(subset=['ppi_growth']).sort_values('date')
        except Exception as e:
            self.logger.error(f"PPI Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window using DateOffset
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: 20 years (240 months)
        df_long = df.iloc[-240:].copy() 
        
        c_ppi = '#2c3e50'    # Dark Navy
        c_growth = '#E74C3C' # Premium Red
        
        # --- Top: Recent (Show Growth % only for clarity) ---
        ax_top = axes[0]
        # Plot Growth % with prominent markers
        ax_top.plot(df_short['date'], df_short['ppi_growth'], 'o-', color=c_growth,
                     linewidth=3, markersize=8, label='PPI同比增长(%)')
        ax_top.axhline(y=0, color='#636e72', linestyle='--', alpha=0.5, linewidth=1)
        
        self.plotter.fmt_single(fig, ax_top,
                             title='宏观数据-PPI价格指数 (近期13月)',
                             ylabel='同比增长(%)',
                             rotation=15,
                             data=df_short['ppi_growth'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History (Show Index trend + Growth bars) ---
        ax_bot = axes[1]
        # Main line: PPI Index (100-based)
        ax_bot.plot(df_long['date'], df_long['ppi_index_yoy'], color=c_ppi, linewidth=2, label='PPI指数(上年=100)')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['ppi_index_yoy'], color=c_ppi)
        
        # Secondary axis for Growth % bars
        ax_bot_r = ax_bot.twinx()
        # Use semi-transparent bars for growth to avoid clutter
        ax_bot_r.bar(df_long['date'], df_long['ppi_growth'], width=20, alpha=0.3, color=c_growth, label='同比涨幅')
        ax_bot_r.axhline(y=0, color='#636e72', linestyle=':', alpha=0.5)
        
        self.plotter.fmt_twinx(fig, ax_bot, ax_bot_r,
                              title='历史走势 (20年)',
                              ylabel_left='指数',
                              ylabel_right='涨幅(%)',
                              rotation=15,
                              data_left=df_long['ppi_index_yoy'],
                              data_right=df_long['ppi_growth'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/ppi.png"
        self.plotter.save(fig, path)
        return path
