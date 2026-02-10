import akshare as ak
import pandas as pd
from .base import BaseIndicator

class InsuranceIndicator(BaseIndicator):
    """中国保险保费收入"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_insurance_income()
            # 日期, 最新值, 涨跌幅, ...
            df = df.rename(columns={
                '日期': 'date',
                '最新值': 'value'
            })
            df['date'] = pd.to_datetime(df['date'])
            df['value'] = pd.to_numeric(df['value'], errors='coerce')
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"Insurance Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        df['date'] = pd.to_datetime(df['date'])
        
        # 1. Standardized 13-month window
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=13)
        df_short = df[df['date'] >= short_threshold].copy()
        
        # History: last 20 years (240 months)
        df_long = df.iloc[-240:].copy() 
        
        c = '#27ae60' # Nephritis Green (Premium)
        
        # Scale to Billion (亿元) - Assuming raw is in 10k (万元)
        # 355,568,700 -> 35,556 亿元 (3.5 Trillion)
        df_short['value_bn'] = df_short['value'] / 10000
        df_long['value_bn'] = df_long['value'] / 10000
        
        # --- Top (Recent) ---
        ax_top = axes[0]
        ax_top.bar(df_short['date'], df_short['value_bn'], color=c, alpha=0.7, width=20, label='总保费收入')
        ax_top.plot(df_short['date'], df_short['value_bn'], 'o-', markersize=8, color=c, linewidth=3)
        
        # Data Labels
        for x, y in zip(df_short['date'], df_short['value_bn']):
            ax_top.text(x, y + (y * 0.02), f'{y:,.0f}', ha='center', va='bottom', fontsize=9, fontweight='bold', color=c)

        self.plotter.fmt_single(fig, ax_top, title='宏观数据-全国保险保费收入 (近期13月)', 
                               ylabel='亿元', rotation=15, 
                               data=df_short['value_bn'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom (History) ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['value_bn'], color=c, linewidth=2)
        # Gradient Fill
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['value_bn'], color=c)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年)', ylabel='亿元', rotation=15, 
                               data=df_long['value_bn'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/insurance.png"
        self.plotter.save(fig, path)
        return path
