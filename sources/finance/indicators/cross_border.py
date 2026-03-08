import akshare as ak
import pandas as pd
from .base import BaseIndicator

class CrossBorderIndicator(BaseIndicator):
    """中美利差 (跨境流动性压力)"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.bond_zh_us_rate()
            df = df.rename(columns={
                '日期': 'date',
                '中国国债收益率10年': 'cn_10y',
                '美国国债收益率10年': 'us_10y'
            })
            df['date'] = pd.to_datetime(df['date'])
            df['cn_10y'] = pd.to_numeric(df['cn_10y'], errors='coerce')
            df['us_10y'] = pd.to_numeric(df['us_10y'], errors='coerce')
            
            # Spread: US - CN (Pressure on CNY)
            df['spread'] = df['us_10y'] - df['cn_10y']
            
            return df.dropna(subset=['cn_10y', 'us_10y']).sort_values('date')
        except Exception as e:
            self.logger.error(f"CrossBorder Fetch Error: {e}")
            return None

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: 10 Years
        # Data available from ~2002, but 10y is enough for regime change
        long_threshold = latest_date - pd.DateOffset(years=10)
        df_long = df[df['date'] >= long_threshold].copy()
        
        c_us = '#2980b9' # Blue
        c_cn = '#c0392b' # Red
        c_spread = '#8e44ad' # Purple
        
        # --- Top: Rates Comparison ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['us_10y'], color=c_us, linewidth=2.5, label='美债10Y')
        ax_top.plot(df_short['date'], df_short['cn_10y'], color=c_cn, linewidth=2.5, label='中债10Y')
        
        self.plotter.draw_current_line(df_short['us_10y'].iloc[-1], ax_top, c_us)
        self.plotter.draw_current_line(df_short['cn_10y'].iloc[-1], ax_top, c_cn)
        
        self.plotter.fmt_single(fig, ax_top, title='跨境流动性-中美10年期国债收益率 (近期13月)', 
                               ylabel='收益率(%)', rotation=15, 
                               data=[df_short['us_10y'], df_short['cn_10y']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: Spread ---
        ax_bot = axes[1]
        
        # Area Chart for Spread
        # Green if US > CN (Pressure), Red if US < CN (Inflow) - Convention debatable
        # Let's keep it simple: Spread Value
        ax_bot.fill_between(df_long['date'], df_long['spread'], 0, where=(df_long['spread']>=0), 
                           color='#27ae60', alpha=0.5, label='美债更高(流出压力)')
        ax_bot.fill_between(df_long['date'], df_long['spread'], 0, where=(df_long['spread']<0), 
                           color='#e74c3c', alpha=0.5, label='中债更高(流入动力)')
        ax_bot.plot(df_long['date'], df_long['spread'], color='#7f8c8d', linewidth=0.8)
        
        # Zero line
        ax_bot.axhline(y=0, color='black', linestyle='-', linewidth=0.8)

        self.plotter.fmt_single(fig, ax_bot, title='利差走势 (美债-中债) (10年)', 
                               ylabel='利差(%)', rotation=15, 
                               data=df_long['spread'])
        self.plotter.set_no_margins(ax_bot)
        ax_bot.legend(loc='upper right', fontsize=8)
        
        path = "output/finance/cross_border.png"
        self.plotter.save(fig, path)
        return path
