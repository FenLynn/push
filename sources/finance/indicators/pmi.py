import akshare as ak
import pandas as pd
from .base import BaseIndicator

class PMIIndicator(BaseIndicator):
    """PMI 采购经理人指数"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_pmi()
            # Parse month to date
            df['date'] = pd.to_datetime(df['月份'], format='%Y年%m月份')
            df = df.rename(columns={
                '制造业-指数': 'manufacture',
                '非制造业-指数': 'non_manufacture'
            })
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"PMI Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        # Use 3:1 ratio layout
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        
        # Data windows - monthly data
        df_short = df.iloc[-12:].copy()    # Recent 12 months (1 year)
        df_long = df.iloc[-240:].copy()    # History 240 months (20 years)
        
        # Colors
        c_manu = '#2ECC71'      # Manufacturing - Green
        c_non = '#3498DB'       # Non-manufacturing - Blue
        
        # --- Top: Recent (1 Year) ---
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['manufacture'], 'o-', color=c_manu,
                   linewidth=2, markersize=5, label='制造业PMI')
        ax_top.plot(df_short['date'], df_short['non_manufacture'], 'D-', color=c_non,
                   linewidth=2, markersize=4, label='非制造业PMI')
        ax_top.axhline(y=50, color='red', linestyle='--', linewidth=1, alpha=0.7, label='荣枯线(50)')
        
        # Current value lines
        try:
            curr_manu = df_short.iloc[-1]['manufacture']
            curr_non = df_short.iloc[-1]['non_manufacture']
            self.plotter.draw_current_line(curr_manu, ax_top, c_manu)
            self.plotter.draw_current_line(curr_non, ax_top, c_non)
        except: pass
        
        # Format top
        self.plotter.fmt_single(fig, ax_top,
                              title='宏观数据-PMI采购经理人指数 (近期)',
                              ylabel='PMI指数',
                              rotation=15)
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History (20 Years) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['manufacture'], color=c_manu, 
                   linewidth=1.5, label='制造业PMI')
        ax_bot.plot(df_long['date'], df_long['non_manufacture'], color=c_non,
                   linewidth=1.5, label='非制造业PMI')
        ax_bot.axhline(y=50, color='red', linestyle='--', linewidth=0.8, alpha=0.5)
        
        # Format bottom with internal title
        self.plotter.fmt_single(fig, ax_bot,
                              title='历史走势 (20年)',
                              ylabel='PMI指数',
                              rotation=15)
        self.plotter.set_no_margins(ax_bot)
        
        # Save
        path = "output/finance/pmi.png"
        self.plotter.save(fig, path)
        return path
