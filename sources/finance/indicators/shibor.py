import akshare as ak
import pandas as pd
from .base import BaseIndicator

class ShiborIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        try:
            terms = {'ON': '隔夜', '3M': '3月', '1Y': '1年'}
            dfs = []
            for k, v in terms.items():
                d = ak.rate_interbank(market="上海银行同业拆借市场", symbol="Shibor人民币", indicator=v)
                d = d[['报告日', '利率']].rename(columns={'报告日': 'date', '利率': k})
                d['date'] = pd.to_datetime(d['date'])
                d = d.set_index('date')
                dfs.append(d)
            
            df = pd.concat(dfs, axis=1).sort_index().reset_index()
            df = pd.concat(dfs, axis=1).sort_index().reset_index()
            df = df.ffill()
            return df
            return df
        except Exception as e:
            self.logger.error(f"Shibor Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: show ~20 years (Daily data, use large N)
        df_long = df.iloc[-5000:].copy() 
        
        # Color Palette - Premium SHIBOR Theme
        c_on = '#95a5a6'   # Silver Gray (超短端背景参考)
        c_3m = '#3498db'   # Dodger Blue (主力合约，视觉主导)
        c_1y = '#9b59b6'   # Amethyst (中长端定价)
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['ON'], color=c_on, linewidth=1.5, label='隔夜', alpha=0.6)
        ax_top.plot(df_short['date'], df_short['3M'], color=c_3m, linewidth=3.5, label='3月期 (主力)', zorder=3)
        ax_top.plot(df_short['date'], df_short['1Y'], color=c_1y, linewidth=2.5, label='1年期')
        
        # Draw current value line for 3M (dominant contract)
        self.plotter.draw_current_line(df_short['3M'].iloc[-1], ax_top, c_3m)
        
        # Explicit legend
        ax_top.legend(loc='upper right', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_single(fig, ax_top, title='流动性-Shibor利率 (近期13月)', 
                               ylabel='利率(%)', rotation=15,
                               data=[df_short['ON'], df_short['3M'], df_short['1Y']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: Long ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['ON'], color=c_on, linewidth=0.8, alpha=0.4)
        ax_bot.plot(df_long['date'], df_long['3M'], color=c_3m, linewidth=1.8, alpha=0.9)
        ax_bot.plot(df_long['date'], df_long['1Y'], color=c_1y, linewidth=1.5, alpha=0.8)
        
        # Gradient fill for 3M
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['3M'], color=c_3m, alpha_top=0.2)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年全景)', 
                               ylabel='利率(%)', rotation=15,
                               data=[df_long['ON'], df_long['3M'], df_long['1Y']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/shibor.png"
        self.plotter.save(fig, path)
        return path
