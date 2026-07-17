import akshare as ak
import pandas as pd
from .base import BaseIndicator
import numpy as np
import requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

class GDPIndicator(BaseIndicator):
    """GDP 国内生产总值"""

    @staticmethod
    def _read_official_yoy_table(report_url: str) -> pd.DataFrame:
        """Parse the first NBS table containing quarterly GDP YoY rates."""
        for table in pd.read_html(report_url):
            if table.shape[1] < 5:
                continue
            header_rows = table.apply(
                lambda row: '|'.join(str(value) for value in row.tolist()), axis=1
            )
            header_index = next((idx for idx, text in header_rows.items()
                                 if '年份' in text and '1季度' in text and '4季度' in text), None)
            if header_index is None:
                continue
            header = [str(value) for value in table.loc[header_index].tolist()[:5]]
            candidate = table.loc[header_index + 1:, table.columns[:5]].copy()
            candidate.columns = header
            candidate['年份'] = pd.to_numeric(candidate['年份'], errors='coerce')
            candidate = candidate.dropna(subset=['年份'])
            rows = []
            for _, row in candidate.iterrows():
                year = int(row['年份'])
                for quarter in range(1, 5):
                    value = pd.to_numeric(row.get(f'{quarter}季度'), errors='coerce')
                    if pd.notna(value):
                        rows.append({'year': year, 'q_end': quarter, 'quarter_yoy': float(value)})
            if rows:
                return pd.DataFrame(rows)
        raise RuntimeError(f'NBS GDP single-quarter YoY table not found: {report_url}')

    @staticmethod
    def _fetch_official_quarter_yoy() -> pd.DataFrame:
        """Read the NBS' latest official *single-quarter* constant-price table."""
        listing_url = 'https://www.stats.gov.cn/sj/zxfb/'
        response = requests.get(listing_url, timeout=20)
        response.raise_for_status()
        soup = BeautifulSoup(response.content, 'html.parser')
        report_url = ''
        for anchor in soup.find_all('a', href=True):
            title = ''.join(anchor.get_text(' ', strip=True).split())
            if '国内生产总值初步核算结果' in title:
                report_url = urljoin(listing_url, anchor['href'])
                break
        if not report_url:
            raise RuntimeError('NBS GDP quarterly report link not found')

        latest = GDPIndicator._read_official_yoy_table(report_url)
        # The latest release currently starts in 2021.  The NBS 2021 annual
        # release supplies the preceding official 2016-2020 single-quarter
        # series, giving the long chart a genuine ten-year window.
        history_url = 'https://www.stats.gov.cn/sj/zxfb/202302/t20230203_1901345.html'
        history = GDPIndicator._read_official_yoy_table(history_url)
        return (
            pd.concat([history, latest], ignore_index=True)
            .drop_duplicates(['year', 'q_end'], keep='last')
            .sort_values(['year', 'q_end'])
            .reset_index(drop=True)
        )

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

            # Nominal quarterly amounts cannot be used to derive real GDP YoY.
            # Merge the NBS constant-price single-quarter series explicitly.
            official_yoy = self._fetch_official_quarter_yoy()
            df = df.merge(official_yoy, on=['year', 'q_end'], how='left')
            
            return df.sort_values('date')
        except Exception as e:
            self.logger.error(f"GDP Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        quarters = df[(df['q_start'] == 1) & df['q_end'].notna()].copy().sort_values('date')
        recent = quarters.tail(8).copy()
        history = quarters.dropna(subset=['quarter_yoy']).copy()
        history = history[history['date'] >= history['date'].max() - pd.DateOffset(years=10)]

        c_single = '#C94F45'
        c_growth = '#2E7FB8'
        ax_top = axes[0]
        x = np.arange(len(recent))
        single_values = recent['gdp_single'] / 10000

        year_palette = ['#3976A8', '#2D8B78', '#8A63B8', '#D28A35']
        bars = []
        for color_index, (year, group) in enumerate(recent.groupby('year', sort=True)):
            positions = np.asarray([recent.index.get_loc(idx) for idx in group.index])
            group_bars = self.plotter.gradient_bars(
                ax_top, positions, group['gdp_single'] / 10000, width=0.58,
                color=year_palette[color_index % len(year_palette)],
                label=f'{int(year)}年', zorder=2,
            )
            bars.extend(group_bars)
        for bar, value in zip(bars, single_values):
            if pd.notna(value):
                ax_top.text(bar.get_x() + bar.get_width() / 2, value, f'{value:.1f}',
                            ha='center', va='bottom', fontsize=11, fontweight='bold', color='#3C4043')
        ax_top.set_xticks(x)
        ax_top.set_xticklabels([f"{int(r.year)}Q{int(r.q_end)}" for _, r in recent.iterrows()])
        ax_top.set_xlim(-0.5, len(recent) - 0.5)

        ax_top_r = ax_top.twinx()
        ax_top_r.plot(x, recent['quarter_yoy'], 'o-', color=c_growth, linewidth=2.4,
                      markersize=6, label='单季度同比', zorder=4)
        ax_top_r.plot(x, recent['gdp_growth'], 'D-', color='#D49A22', linewidth=1.8,
                      markersize=5, label='年内累计同比', zorder=4)
        self.plotter.fmt_twinx(
            fig, ax_top, ax_top_r, title='GDP：近8个季度规模与增速',
            ylabel_left='GDP（万亿元）', ylabel_right='同比（%）', rotation=0,
            data_left=single_values,
            data_right=[recent['quarter_yoy'], recent['gdp_growth']],
        )

        ax_bot = axes[1]
        self.plotter.fill_diverging_gradient(ax_bot, history['date'], history['quarter_yoy'],
                                             positive_color='#C95A55', negative_color='#3D8B68',
                                             alpha_top=0.28, zorder=1)
        ax_bot.plot(history['date'], history['quarter_yoy'], color=c_growth,
                    linewidth=2, label='单季度同比', zorder=4)
        ax_bot.axhline(y=0, color='#636e72', linestyle='--', linewidth=0.8, alpha=0.5)
        self.plotter.fmt_single(fig, ax_bot, title='官方单季度同比（最近10年）',
                               ylabel='同比(%)', rotation=15, data=history['quarter_yoy'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/gdp.png"
        self.plotter.save(fig, path)
        return path
