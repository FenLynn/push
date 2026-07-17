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
            df = df.sort_values('date').dropna(subset=['date', 'pe'])
            try:
                index = ak.stock_zh_index_daily(symbol='sh000001')[['date', 'close']].copy()
                index['date'] = pd.to_datetime(index['date'])
                index['sh_close'] = pd.to_numeric(index['close'], errors='coerce')
                self._sh_index = index[['date', 'sh_close']].dropna().sort_values('date')
                df = df.merge(index[['date', 'sh_close']], on='date', how='left')
            except Exception:
                self._sh_index = pd.DataFrame(columns=['date', 'sh_close'])
                df['sh_close'] = pd.NA
            return df
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
        
        self.plotter.fmt_single(fig, ax_top, title='上证平均市盈率（月度，近2年）',
                               ylabel='PE (倍)', rotation=15, 
                               data=df_short['pe'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: 10Y History ---
        ax_bot = axes[1]
        baseline = df_long['pe'].min() * 0.96
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['pe'],
                                   color=c_pe, alpha_top=0.16, baseline=baseline, zorder=1)
        ax_bot.plot(df_long['date'], df_long['pe'], color=c_pe, linewidth=1.5,
                    label='上证平均PE', zorder=4)
        ax_bot_r = ax_bot.twinx()
        sh_history = getattr(self, '_sh_index', pd.DataFrame())
        if not sh_history.empty:
            sh_history = sh_history[sh_history['date'] >= long_threshold]
        else:
            sh_history = df_long[['date', 'sh_close']]
        ax_bot_r.plot(sh_history['date'], sh_history['sh_close'], color='#3976A8',
                      linewidth=1.2, alpha=0.78, label='上证指数', zorder=3)
        self.plotter.fmt_twinx(fig, ax_bot, ax_bot_r, title='上证PE与指数（10年）',
                               ylabel_left='PE', ylabel_right='上证指数', rotation=15,
                               data_left=df_long['pe'], data_right=sh_history['sh_close'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/market_pe.png"
        self.plotter.save(fig, path)
        return path
