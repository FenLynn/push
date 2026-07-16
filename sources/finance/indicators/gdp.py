import akshare as ak
import pandas as pd
from .base import BaseIndicator
import numpy as np

class GDPIndicator(BaseIndicator):
    """GDP 国内生产总值"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            df = ak.macro_china_gdp()
            
            # Parse quarter to date
            def parse_quarter_info(q_str):
                import re
                match = re.search(r'(\d{4})年第(\d+)(?:-(\d+))?季度', q_str)
                if match:
                    year = int(match.group(1))
                    q_start = int(match.group(2))
                    q_end = int(match.group(3)) if match.group(3) else int(match.group(2))
                    month = q_end * 3
                    date = pd.Timestamp(year=year, month=month, day=1) + pd.offsets.MonthEnd(0)
                    return pd.Series({'date': date, 'year': year, 'q_start': q_start, 'q_end': q_end})
                return pd.Series({'date': pd.NaT, 'year': None, 'q_start': None, 'q_end': None})
            
            quarter_info = df['季度'].apply(parse_quarter_info)
            df = pd.concat([df, quarter_info], axis=1)
            
            df = df.rename(columns={
                '国内生产总值-绝对值': 'gdp_cumulative',
                '国内生产总值-同比增长': 'gdp_growth'
            })
            
            df = df.sort_values(['year', 'q_end'])
            df['gdp_single'] = df['gdp_cumulative']
            
            for year in df['year'].dropna().unique():
                year_mask = df['year'] == year
                for q in [2, 3, 4]:
                    curr_q_mask = year_mask & (df['q_end'] == q) & (df['q_start'] == 1)
                    prev_q_mask = year_mask & (df['q_end'] == q-1) & (df['q_start'] == 1)
                    
                    if curr_q_mask.any() and prev_q_mask.any():
                        curr_val = df.loc[curr_q_mask, 'gdp_cumulative'].values[0]
                        prev_val = df.loc[prev_q_mask, 'gdp_cumulative'].values[0]
                        df.loc[curr_q_mask, 'gdp_single'] = curr_val - prev_val
            
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"GDP Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # Consistent window for GDP (Quarterly, so 6 quarters ~ 18 months to see > 1 year)
        latest_date = df['date'].max()
        short_threshold = latest_date - pd.DateOffset(months=18)
        df_short = df[df['date'] >= short_threshold].copy()
        
        df_long = df[df['q_start'] == 1].copy() 
        df_long = df_long.iloc[-80:] # 20 Years
        
        c_single = '#C94F45'      # 单季度规模
        c_growth = '#2E7FB8'      # 累计同比增速
        
        # --- Top ---
        ax_top = axes[0]
        x = np.arange(len(df_short))
        width = 0.58
        single_values = df_short['gdp_single'] / 10000

        # 单季度值与累计值不能堆叠；堆叠会重复计算同一季度产出。
        bars = ax_top.bar(
            x,
            single_values,
            width,
            label='单季度GDP（万亿元）',
            color=c_single,
            alpha=0.9,
            edgecolor='none',
            zorder=2,
        )
        for bar, value in zip(bars, single_values):
            if pd.notna(value):
                ax_top.text(
                    bar.get_x() + bar.get_width() / 2,
                    bar.get_height(),
                    f'{value:.1f}',
                    ha='center',
                    va='bottom',
                    fontsize=8,
                    color='#3C4043',
                    fontweight='bold',
                )
        
        def get_label(row):
            q = int(row['q_end'])
            return f"{int(row['year'])} Q{q}"
        ax_top.set_xticks(x)
        ax_top.set_xticklabels([get_label(r) for idx, r in df_short.iterrows()])
        
        # Growth Rate Line (Secondary Axis)
        ax_top_r = ax_top.twinx()
        ax_top_r.plot(
            x,
            df_short['gdp_growth'],
            'D-',
            color=c_growth,
            linewidth=2.5,
            markersize=6,
            label='GDP累计同比（%）',
            zorder=3,
        )
        
        self.plotter.fmt_twinx(
            fig,
            ax_top,
            ax_top_r,
            title='GDP：单季度规模与累计同比（近期对比）',
            ylabel_left='单季度GDP（万亿元）',
            ylabel_right='累计同比（%）',
            rotation=0,
            data_left=single_values,
            data_right=df_short['gdp_growth'],
        )
        
        # --- Bottom ---
        ax_bot = axes[1]
        ax_bot.plot(df_long['date'], df_long['gdp_growth'], color=c_growth, linewidth=2, label='GDP同比')
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['gdp_growth'], color=c_growth)
        ax_bot.axhline(y=0, color='#636e72', linestyle='--', linewidth=0.8, alpha=0.5)
        
        self.plotter.fmt_single(fig, ax_bot, title='历史走势 (20年全景)', ylabel='增速(%)', rotation=15, 
                               data=df_long['gdp_growth'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/gdp.png"
        self.plotter.save(fig, path)
        return path
