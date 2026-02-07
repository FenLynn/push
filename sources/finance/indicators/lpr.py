import akshare as ak
import pandas as pd
from .base import BaseIndicator

class LPRIndicator(BaseIndicator):
    """LPR 及 贷款基准利率"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_lpr()
            # TRADE_DATE, LPR1Y, LPR5Y, RATE_1, RATE_2
            df = df.rename(columns={
                'TRADE_DATE': 'date',
                'LPR1Y': 'lpr1y',
                'LPR5Y': 'lpr5y',
                'RATE_1': 'rate1',
                'RATE_2': 'rate2'
            })
            df['date'] = pd.to_datetime(df['date'])
            # Ensure numeric
            for col in ['lpr1y', 'lpr5y', 'rate1', 'rate2']:
                df[col] = pd.to_numeric(df[col], errors='coerce')
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"LPR Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show all or last 20 years
        df_long = df.iloc[-240:].copy() 
        
        c1 = '#E74C3C' # LPR1Y - Red
        c2 = '#273c75' # LPR5Y - Blue
        c3 = '#bdc3c7' # Benchmarks - Light Gray
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        ax_top.step(df_short['date'], df_short['lpr1y'], where='post', color=c1, linewidth=3, label='LPR 1Y')
        ax_top.step(df_short['date'], df_short['lpr5y'], where='post', color=c2, linewidth=3, label='LPR 5Y')
        
        # Benchmarks as dotted lines if needed
        ax_top.step(df_short['date'], df_short['rate1'], where='post', color=c3, linewidth=1, linestyle='--', label='基准(1Y)')
        
        self.plotter.fmt_single(fig, ax_top, title='金融利率-LPR 贷款报价利率 (近期13月)', 
                               ylabel='利率 (%)', rotation=15, 
                               data=[df_short['lpr1y'], df_short['lpr5y']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom (History) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['lpr1y'], color=c1, linewidth=1.5, label='LPR 1Y')
        ax_bot.plot(df_long['date'], df_long['lpr5y'], color=c2, linewidth=1.5, label='LPR 5Y')
        ax_bot.plot(df_long['date'], df_long['rate1'], color='#7f8c8d', linewidth=1, alpha=0.5, label='基准(1Y)')
        
        # Gradient Fill for LPR1Y
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['lpr1y'], color=c1, alpha_top=0.2)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (含基准利率)', ylabel='利率 (%)', rotation=15, 
                               data=[df_long['lpr1y'], df_long['lpr5y']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/lpr.png"
        self.plotter.save(fig, path)
        return path
