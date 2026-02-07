
import akshare as ak
import pandas as pd
from .base import BaseIndicator

class ShiborIndicator(BaseIndicator):
    def fetch_data(self) -> pd.DataFrame:
        """Fetch Shibor Rates"""
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
            df = df.fillna(method='ffill')
            return df
        except Exception as e:
            self.logger.error(f"Shibor Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        df['date'] = pd.to_datetime(df['date'])
        df_long = df.iloc[-5000:].copy() 
        df_short = df.iloc[-250:].copy() 
        
        # Top: Recent
        ax_top = axes[0]
        ax_top.plot(df_short['date'], df_short['ON'], color='silver', linewidth=1, label='隔夜')
        ax_top.plot(df_short['date'], df_short['3M'], color='orange', linewidth=2, label='3月')
        ax_top.plot(df_short['date'], df_short['1Y'], color='cornflowerblue', linewidth=2, label='1年')
        
        self.plotter.draw_current_line(df_short['3M'].iloc[-1], ax_top, 'orange')
        
        self.plotter.fmt_single(fig, ax_top, title='流动性-Shibor利率 (近期)', ylabel='利率(%)', rotation=45)
        self.plotter.set_no_margins(ax_top)
        
        # Bottom: Long
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['ON'], color='silver', linewidth=0.5)
        ax_bot.plot(df_long['date'], df_long['3M'], color='orange', linewidth=1)
        ax_bot.plot(df_long['date'], df_long['1Y'], color='cornflowerblue', linewidth=1)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势', ylabel='利率(%)', rotation=45)
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/shibor.png"
        self.plotter.save(fig, path)
        return path
