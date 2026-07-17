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
            df = df.sort_values('date').dropna(subset=['lpr1y', 'lpr5y']).copy()
            changed = df['lpr1y'].ne(df['lpr1y'].shift()) | df['lpr5y'].ne(df['lpr5y'].shift())
            df['unchanged_months'] = df.groupby(changed.cumsum()).cumcount() + 1
            return df
        except Exception as e:
            self.logger.error(f"LPR Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        df_short = df.tail(15).copy()
        
        # History: show all or last 20 years
        df_long = df.iloc[-240:].copy() 
        
        # Color Palette - Premium LPR Theme
        c_1y = '#e74c3c'  # Crimson (短期贷款基准)
        c_5y = '#2c3e50'  # Midnight Blue (房贷基准)
        c_benchmark = '#ecf0f1'  # Very Light Gray (历史参考，弱化)
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        ax_top.step(df_short['date'], df_short['lpr1y'], where='post', color=c_1y, linewidth=3.5, label='LPR 1Y', zorder=3)
        ax_top.step(df_short['date'], df_short['lpr5y'], where='post', color=c_5y, linewidth=3, label='LPR 5Y', zorder=2)
        current = df_short.iloc[-1]
        ax_top.text(
            0.02, 0.96,
            f"现值：1Y {current['lpr1y']:.2f}% · 5Y {current['lpr5y']:.2f}% · 已持续 {int(current['unchanged_months'])} 个月",
            transform=ax_top.transAxes, va='top', ha='left', fontsize=10, color='#4B5563',
        )
        
        # Benchmarks as faint dotted lines (weakened)
        if 'rate1' in df_short.columns:
            ax_top.step(df_short['date'], df_short['rate1'], where='post', color=c_benchmark, 
                       linewidth=1, linestyle='--', alpha=0.4, label='基准利率(1Y)', zorder=1)
        
        # Draw current value line for LPR 1Y
        self.plotter.draw_current_line(df_short['lpr1y'].iloc[-1], ax_top, c_1y)
        
        # Explicit legend
        ax_top.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='LPR 贷款报价利率（近15个月）',
                               ylabel='利率 (%)', rotation=15, 
                               data=[df_short['lpr1y'], df_short['lpr5y']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom (History) ---
        ax_bot = axes[1]
        baseline = min(df_long['lpr1y'].min(), df_long['lpr5y'].min()) * 0.96
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['lpr1y'], color=c_1y,
                                   alpha_top=0.22, baseline=baseline, zorder=1, step='post')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['lpr5y'], color=c_5y,
                                   alpha_top=0.14, baseline=baseline, zorder=1, step='post')
        ax_bot.step(df_long['date'], df_long['lpr1y'], where='post', color=c_1y,
                    linewidth=1.8, alpha=0.95, label='LPR 1Y', zorder=3)
        ax_bot.step(df_long['date'], df_long['lpr5y'], where='post', color=c_5y,
                    linewidth=1.5, alpha=0.9, label='LPR 5Y', zorder=3)
        
        if 'rate1' in df_long.columns:
            ax_bot.plot(df_long['date'], df_long['rate1'], color='#bdc3c7', linewidth=0.8, 
                       alpha=0.3, linestyle='--', label='基准(1Y)')
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (含基准利率参考)', 
                               ylabel='利率 (%)', rotation=15, 
                               data=[df_long['lpr1y'], df_long['lpr5y']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/lpr.png"
        self.plotter.save(fig, path)
        return path
