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
        quarters = df[(df['q_start'] == 1) & df['q_end'].notna()].copy().sort_values('date')
        quarters['quarter_yoy'] = quarters.groupby('q_end')['gdp_single'].pct_change() * 100
        recent = quarters.tail(8).copy()
        history = quarters.tail(80).copy()

        c_single = '#C94F45'
        c_growth = '#2E7FB8'
        c_cumulative = '#8A94A0'
        ax_top = axes[0]
        x = np.arange(len(recent))
        single_values = recent['gdp_single'] / 10000

        # 每个年份用一根淡色宽柱表示当前图中该年的季度合计；完整年度与
        # 不完整年度均按实际可见季度求和，避免把半年累计伪装成全年值。
        for year, group in recent.groupby('year', sort=True):
            positions = [recent.index.get_loc(idx) for idx in group.index]
            left, right = min(positions), max(positions)
            annual_visible = group['gdp_single'].sum() / 10000
            ax_top.bar((left + right) / 2, annual_visible, width=(right - left + 0.9),
                       color=c_cumulative, alpha=0.11, edgecolor='none', zorder=0,
                       label='年度/年内合计' if year == recent['year'].min() else None)

        bars = ax_top.bar(x, single_values, width=0.56, color=c_single, alpha=0.88,
                          edgecolor='none', label='单季度GDP', zorder=2)
        for bar, value in zip(bars, single_values):
            if pd.notna(value):
                ax_top.text(bar.get_x() + bar.get_width() / 2, value, f'{value:.1f}',
                            ha='center', va='bottom', fontsize=8, color='#3C4043')
        ax_top.set_xticks(x)
        ax_top.set_xticklabels([f"{int(r.year)} Q{int(r.q_end)}" for _, r in recent.iterrows()])

        ax_top_r = ax_top.twinx()
        ax_top_r.plot(x, recent['quarter_yoy'], 'o-', color=c_growth, linewidth=2.4,
                      markersize=6, label='单季度同比', zorder=4)
        ax_top_r.plot(x, recent['gdp_growth'], 'D--', color='#D49A22', linewidth=1.8,
                      markersize=5, label='年内累计同比', zorder=4)
        self.plotter.fmt_twinx(
            fig, ax_top, ax_top_r, title='GDP：近8个季度规模与增速',
            ylabel_left='GDP（万亿元）', ylabel_right='同比（%）', rotation=0,
            data_left=[single_values, recent.groupby('year')['gdp_single'].transform('sum') / 10000],
            data_right=[recent['quarter_yoy'], recent['gdp_growth']],
        )

        ax_bot = axes[1]
        self.plotter.fill_diverging_gradient(ax_bot, history['date'], history['quarter_yoy'],
                                             positive_color=c_growth, negative_color='#3D8B68',
                                             alpha_top=0.28, zorder=1)
        ax_bot.plot(history['date'], history['quarter_yoy'], color=c_growth,
                    linewidth=2, label='单季度同比', zorder=4)
        ax_bot.axhline(y=0, color='#636e72', linestyle='--', linewidth=0.8, alpha=0.5)
        self.plotter.fmt_single(fig, ax_bot, title='单季度同比长期走势（20年）',
                               ylabel='同比(%)', rotation=15, data=history['quarter_yoy'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/gdp.png"
        self.plotter.save(fig, path)
        return path
