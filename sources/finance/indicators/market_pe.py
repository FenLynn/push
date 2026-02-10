import akshare as ak
import pandas as pd
import numpy as np
from .base import BaseIndicator

class MarketPEIndicator(BaseIndicator):
    """全A市场估值 (上证平均市盈率)"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            # Using Legu source for Shanghai Exchange PE
            df = ak.stock_market_pe_lg(symbol="上证")
            df = df.rename(columns={
                '日期': 'date',
                '平均市盈率': 'pe'
            })
            df['date'] = pd.to_datetime(df['date'])
            df['pe'] = pd.to_numeric(df['pe'], errors='coerce')
            return df.sort_values('date').dropna()
        except Exception as e:
            self.logger.error(f"Market PE Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Recent 2 Years (for clearer short term view) instead of 13 months
        # Valuation needs a bit more context
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(years=2)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: 10 Years
        long_threshold = latest_date - pd.DateOffset(years=10)
        df_long = df[df['date'] >= long_threshold].copy()
        
        c_pe = '#8e44ad' # Wisteria Purple (Premium)
        
        # Calculate Quantiles (based on 10y history)
        q10 = df_long['pe'].quantile(0.10)
        q50 = df_long['pe'].quantile(0.50)
        q90 = df_long['pe'].quantile(0.90)
        
        # --- Top: Recent Trend with Bands ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['pe'], color=c_pe, linewidth=2.5, label='上证平均PE')
        
        # Add bands
        ax_top.axhline(y=q90, color='#e74c3c', linestyle='--', alpha=0.5, label='高估(90%)')
        ax_top.axhline(y=q50, color='#f1c40f', linestyle='--', alpha=0.5, label='中枢(50%)')
        ax_top.axhline(y=q10, color='#27ae60', linestyle='--', alpha=0.5, label='低估(10%)')
        
        # Fill between to show current zone
        # No, just lines is cleaner.
        
        # Current Label
        current_pe = df_short['pe'].iloc[-1]
        self.plotter.draw_current_line(current_pe, ax_top, c_pe)
        
        # Percentile rank
        rank = (df_long['pe'] < current_pe).mean() * 100
        ax_top.text(df_short['date'].iloc[0], current_pe, f" 当前分位: {rank:.1f}%", 
                   color=c_pe, fontsize=10, fontweight='bold', ha='left', va='bottom')
        
        self.plotter.fmt_single(fig, ax_top, title='市场估值锚-上证平均市盈率 (近期2年)', 
                               ylabel='PE (倍)', rotation=15, 
                               data=df_short['pe'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: 10Y History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['pe'], color=c_pe, linewidth=1.5)
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['pe'], color=c_pe)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史估值走势 (10年)', 
                               ylabel='PE', rotation=15, 
                               data=df_long['pe'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/market_pe.png"
        self.plotter.save(fig, path)
        return path
