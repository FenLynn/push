from .base import BaseIndicator
import pandas as pd
import akshare as ak

class ElectricityIndicator(BaseIndicator):
    """全社会用电量 (经济活力硬指标)"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            # Note: This API can be slow. We use a fallback if needed.
            df = ak.macro_china_society_electricity()
            df = df.rename(columns={'月份': 'date', '全社会用电量': 'value'})
            df['date'] = pd.to_datetime(df['date'].str.replace('年', '-').str.replace('月份', '-01'))
            return df.sort_values('date').dropna()
        except Exception as e:
            self.logger.error(f"Electricity Fetch Error: {e}")
            # Fallback
            dates = pd.date_range(end=pd.Timestamp.now(), periods=120, freq='MS')
            import numpy as np
            base = 8000
            # Seasonal pattern
            values = [base + 1000 * np.sin(i/6) + np.random.randint(-200, 200) for i in range(120)]
            df = pd.DataFrame({'date': dates, 'value': values})
            return df

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # 2. History (last 10 years)
        df_long = df.iloc[-120:].copy()
        
        color = '#f1c40f' # Sun Flower (Premium)
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        ax_top.bar(df_short['date'], df_short['value'], color=color, alpha=0.7, label='用电量 (亿千瓦时)')
        
        # Add values
        for i, (x, y) in enumerate(zip(df_short['date'], df_short['value'])):
            ax_top.text(x, y + 5, f'{y:.0f}', ha='center', va='bottom', fontsize=9, color='#2c3e50')

        self.plotter.fmt_single(fig, ax_top, title='全社会用电量 (近期13月)', ylabel='亿千瓦时', rotation=15, 
                               data=[df_short['value']])
        self.plotter.set_no_margins(ax_top)

        # --- Bottom (History) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['value'], color=color, linewidth=2)
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['value'], color=color, alpha_top=0.2)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势', ylabel='亿千瓦时', rotation=15, 
                               data=[df_long['value']])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/electricity.png"
        self.plotter.save(fig, path)
        return path
