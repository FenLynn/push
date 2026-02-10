import akshare as ak
import pandas as pd
from .base import BaseIndicator

class M1M2GapIndicator(BaseIndicator):
    """M1-M2 剪刀差 (市场活化度指标)"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            # ak.macro_china_money_supply() can hang
            df = ak.macro_china_supply_of_money()
            df['date'] = pd.to_datetime(df['统计时间'], format='%Y.%m')
            
            df = df.rename(columns={
                '货币(狭义货币M1)同比增长': 'm1_growth',
                '货币和准货币（广义货币M2）同比增长': 'm2_growth'
            })
            df['date'] = pd.to_datetime(df['date'])
            df['m1_growth'] = pd.to_numeric(df['m1_growth'], errors='coerce')
            df['m2_growth'] = pd.to_numeric(df['m2_growth'], errors='coerce')
            
            # Calculate Gap: M1 - M2
            # Positive: Activation (Bullish)
            # Negative: Passivation (Bearish)
            df['gap'] = df['m1_growth'] - df['m2_growth']
            
            return df.sort_values('date').dropna(subset=['gap'])
        except Exception as e:
            self.logger.error(f"M1-M2 Gap Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: 20 years
        df_long = df.iloc[-240:].copy() 
        
        c_m1 = '#e67e22' # Carrot Orange (Active)
        c_m2 = '#2c3e50' # Midnight Blue (Broad)
        c_pos = '#e74c3c' # Red for Positive Gap
        c_neg = '#27ae60' # Green for Negative Gap
        
        # --- Top: Recent M1 vs M2 ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['m1_growth'], 'o-', 
                   color=c_m1, linewidth=2.5, label='M1同比(活钱)')
        ax_top.plot(df_short['date'], df_short['m2_growth'], 's-', 
                   color=c_m2, linewidth=2.5, label='M2同比(广义)')
        
        # Draw current lines
        self.plotter.draw_current_line(df_short['m1_growth'].iloc[-1], ax_top, c_m1)
        self.plotter.draw_current_line(df_short['m2_growth'].iloc[-1], ax_top, c_m2)
        
        self.plotter.fmt_single(fig, ax_top, title='市场活化度-M1 vs M2增速 (近期13月)', 
                               ylabel='同比(%)', rotation=15, 
                               data=[df_short['m1_growth'], df_short['m2_growth']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: Historical Gap ---
        ax_bot = axes[1]
        
        # Conditional Bar Colors
        colors = [c_pos if v >= 0 else c_neg for v in df_long['gap']]
        
        ax_bot.bar(df_long['date'], df_long['gap'], color=colors, width=20, alpha=0.8, label='M1-M2剪刀差')
        ax_bot.axhline(y=0, color='#95a5a6', linestyle='--', linewidth=1)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史剪刀差 (正值=市场活化)', 
                               ylabel='Gap (%)', rotation=15, 
                               data=df_long['gap'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/m1_m2_gap.png"
        self.plotter.save(fig, path)
        return path
