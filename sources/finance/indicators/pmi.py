import akshare as ak
import pandas as pd
from .base import BaseIndicator

class PMIIndicator(BaseIndicator):
    """PMI 采购经理人指数"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_pmi()
            df['date'] = pd.to_datetime(df['月份'], format='%Y年%m月份')
            df = df.rename(columns={'制造业-指数': 'manufacture', '非制造业-指数': 'non_manufacture'})
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"PMI Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: 20 years (240 months)
        df_long = df.iloc[-240:].copy() 
        
        c_manu = '#273c75' # Energy Blue
        c_non = '#E74C3C'  # Premium Red
        c_line = '#16a085' # Dark Green for Boom-Bust line (User Request)
        
        # --- Top: Recent ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['manufacture'], 'o-', color=c_manu, linewidth=3, markersize=8, label='制造业PMI')
        ax_top.plot(df_short['date'], df_short['non_manufacture'], 'D-', color=c_non, linewidth=2.5, markersize=7, label='非制造业PMI')
        
        # Boom-bust line (50)
        ax_top.axhline(y=50, color=c_line, linestyle='--', linewidth=2, alpha=0.9, label='荣枯线(50)')
        
        self.plotter.draw_current_line(df_short.iloc[-1]['manufacture'], ax_top, c_manu)
        
        self.plotter.fmt_single(fig, ax_top, title='宏观数据-PMI采购经理人指数 (近期13月)', ylabel='指数', rotation=15,
                               data=[df_short['manufacture'], df_short['non_manufacture']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['manufacture'], color=c_manu, linewidth=2, label='制造业')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['manufacture'], color=c_manu)
        
        ax_bot.axhline(y=50, color=c_line, linestyle=':', alpha=0.6)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年)', ylabel='PMI', rotation=15,
                               data=[df_long['manufacture'], df_long['non_manufacture']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/pmi.png"
        self.plotter.save(fig, path)
        return path
