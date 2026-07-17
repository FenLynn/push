import akshare as ak
import pandas as pd
from .base import BaseIndicator

class M2Indicator(BaseIndicator):
    """M2 货币供应量"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            # ak.macro_china_money_supply() is broken/hanging
            df = ak.macro_china_supply_of_money()
            
            # Column Mapping
            # '统计时间', '货币和准货币（广义货币M2）', '货币和准货币（广义货币M2）同比增长', ...
            df['date'] = pd.to_datetime(df['统计时间'], format='%Y.%m')
            
            df = df.rename(columns={
                '货币和准货币（广义货币M2）': 'm2',
                '货币(狭义货币M1)': 'm1',
                '流通中现金(M0)': 'm0',
                '货币和准货币（广义货币M2）同比增长': 'm2_growth',
                '货币(狭义货币M1)同比增长': 'm1_growth'
            })
            
            # Numeric conversion
            for col in ['m2', 'm1', 'm0', 'm2_growth', 'm1_growth']:
                if col in df.columns:
                    df[col] = pd.to_numeric(df[col], errors='coerce')

            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"M2 Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        df_short = df.tail(15).copy()
        
        # History: 20 years (240 months)
        df_long = df.iloc[-240:].copy() 
        
        c_m2 = '#3976A8'
        c_growth = '#c0392b' # Growth - Deep Red
        
        # --- Top: Recent ---
        ax_top = axes[0]
        # M2 Total (万亿)
        self.plotter.gradient_bars(
            ax_top, df_short['date'], df_short['m2'] / 10000, width=20,
            color=c_m2, label='M2总量(万亿)'
        )
        
        # Growth Rate (Right Axis)
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(df_short['date'], df_short['m2_growth'], 'D-',
                     color=c_growth, linewidth=2, markersize=7, 
                     markeredgecolor='white', markeredgewidth=1, label='M2增速(%)')
        
        self.plotter.draw_current_line(df_short.iloc[-1]['m2']/10000, ax_top, c_m2)
        
        # Combine Legends
        h1, l1 = ax_top.get_legend_handles_labels()
        h2, l2 = ax_top_r.get_legend_handles_labels()
        ax_top.legend(h1+h2, l1+l2, loc='upper left', frameon=True, framealpha=0.9, fontsize=9)
        
        self.plotter.fmt_twinx(fig, ax_top, ax_top_r,
                             title='货币供应量M2（近15个月）',
                             ylabel_left='总量(万亿元)',
                             ylabel_right='同比增长(%)',
                             rotation=15,
                             data_left=df_short['m2']/10000,
                             data_right=df_short['m2_growth'])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        total_long = df_long['m2'] / 10000
        total_baseline = total_long.min() * 0.96
        self.plotter.fill_gradient(ax_bot, df_long['date'], total_long, color=c_m2,
                                   alpha_top=0.22, baseline=total_baseline, zorder=1)
        ax_bot.plot(df_long['date'], total_long, color=c_m2, linewidth=1.8,
                    label='M2总量', zorder=3)
        ax_bot_r = ax_bot.twinx()
        ax_bot_r.plot(df_long['date'], df_long['m2_growth'], color=c_growth,
                      linewidth=1.6, label='M2同比', zorder=4)
        ax_bot.axhline(y=0, color='#95a5a6', linestyle='--', linewidth=0.8, alpha=0.5)
        
        self.plotter.fmt_twinx(fig, ax_bot, ax_bot_r, title='历史走势（20年M2总量与同比）',
                               ylabel_left='总量(万亿元)', ylabel_right='同比(%)', rotation=15,
                               data_left=total_long, data_right=df_long['m2_growth'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/m2.png"
        self.plotter.save(fig, path)
        return path
