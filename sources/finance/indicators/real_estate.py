from concurrent.futures import ThreadPoolExecutor

import pandas as pd
import requests

from .base import BaseIndicator


class RealEstateIndicator(BaseIndicator):
    """70-city residential price breadth replacing the discontinued climate index."""

    CITIES = [
        '北京', '天津', '石家庄', '太原', '呼和浩特', '沈阳', '大连', '长春', '哈尔滨',
        '上海', '南京', '杭州', '宁波', '合肥', '福州', '厦门', '南昌', '济南', '青岛',
        '郑州', '武汉', '长沙', '广州', '深圳', '南宁', '海口', '重庆', '成都', '贵阳',
        '昆明', '西安', '兰州', '西宁', '银川', '乌鲁木齐', '唐山', '秦皇岛', '包头',
        '丹东', '锦州', '吉林', '牡丹江', '无锡', '徐州', '扬州', '温州', '金华', '蚌埠',
        '安庆', '泉州', '九江', '赣州', '烟台', '济宁', '洛阳', '平顶山', '宜昌',
        '襄阳', '岳阳', '常德', '韶关', '湛江', '惠州', '桂林', '北海', '三亚', '泸州',
        '南充', '遵义', '大理',
    ]
    API_URL = 'https://datacenter-web.eastmoney.com/api/data/v1/get'

    @classmethod
    def _params(cls, start_date: str, page: int) -> dict:
        cities = ','.join(f'"{city}"' for city in cls.CITIES)
        return {
            'reportName': 'RPT_ECONOMY_HOUSE_PRICE',
            'columns': (
                'REPORT_DATE,CITY,FIRST_COMHOUSE_SAME,FIRST_COMHOUSE_SEQUENTIAL,'
                'SECOND_HOUSE_SAME,SECOND_HOUSE_SEQUENTIAL'
            ),
            'filter': f"(CITY in ({cities}))(REPORT_DATE>='{start_date}')",
            'pageNumber': str(page),
            'pageSize': '500',
            'sortColumns': 'REPORT_DATE,CITY',
            'sortTypes': '-1,-1',
            'source': 'WEB',
            'client': 'WEB',
        }

    @classmethod
    def _fetch_page(cls, start_date: str, page: int) -> dict:
        response = requests.get(cls.API_URL, params=cls._params(start_date, page), timeout=25)
        response.raise_for_status()
        payload = response.json()
        if not payload.get('success') or not payload.get('result'):
            raise RuntimeError(f"70-city house-price page {page} returned no data")
        return payload['result']

    @staticmethod
    def _aggregate(raw: pd.DataFrame) -> pd.DataFrame:
        required = {
            'REPORT_DATE', 'CITY', 'FIRST_COMHOUSE_SAME', 'FIRST_COMHOUSE_SEQUENTIAL',
            'SECOND_HOUSE_SAME', 'SECOND_HOUSE_SEQUENTIAL',
        }
        if raw is None or raw.empty or not required.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[list(required)].copy()
        frame['date'] = pd.to_datetime(frame['REPORT_DATE'], errors='coerce')
        numeric = [
            'FIRST_COMHOUSE_SAME', 'FIRST_COMHOUSE_SEQUENTIAL',
            'SECOND_HOUSE_SAME', 'SECOND_HOUSE_SEQUENTIAL',
        ]
        frame[numeric] = frame[numeric].apply(pd.to_numeric, errors='coerce')
        frame = frame.dropna(subset=['date', 'CITY']).drop_duplicates(['date', 'CITY'])

        def summarize(group: pd.DataFrame) -> pd.Series:
            return pd.Series({
                # NBS publishes index levels with the comparison period = 100.
                'new_house_yoy': group['FIRST_COMHOUSE_SAME'].median() - 100,
                'second_house_yoy': group['SECOND_HOUSE_SAME'].median() - 100,
                'new_house_rise_share': group['FIRST_COMHOUSE_SEQUENTIAL'].gt(100).mean() * 100,
                'second_house_rise_share': group['SECOND_HOUSE_SEQUENTIAL'].gt(100).mean() * 100,
                'city_count': group['CITY'].nunique(),
            })

        result = frame.groupby('date', as_index=False).apply(
            summarize, include_groups=False
        ).reset_index()
        result = result.drop(columns=['level_0', 'index'], errors='ignore')
        return result[result['city_count'] >= 60].sort_values('date').reset_index(drop=True)

    def fetch_data(self) -> pd.DataFrame:
        start_date = (pd.Timestamp.now(tz='Asia/Shanghai') - pd.DateOffset(years=10)).strftime('%Y-%m-01')
        first = self._fetch_page(start_date, 1)
        pages = int(first.get('pages') or 1)
        records = list(first.get('data') or [])
        if pages > 1:
            with ThreadPoolExecutor(max_workers=6) as executor:
                for result in executor.map(
                    lambda page: self._fetch_page(start_date, page), range(2, pages + 1)
                ):
                    records.extend(result.get('data') or [])
        frame = self._aggregate(pd.DataFrame(records))
        if frame.empty:
            raise RuntimeError('70-city residential price series returned no valid observations')
        return frame

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values('date').copy()
        recent = frame.tail(15)
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        new_color = '#3976A8'
        used_color = '#C95A55'

        self.plotter.fill_diverging_gradient(
            axes[0], recent['date'], recent['new_house_yoy'], baseline=0,
            positive_color='#C95A55', negative_color='#3D8B68', alpha_top=0.34, zorder=1,
        )
        axes[0].plot(recent['date'], recent['new_house_yoy'], color=new_color,
                     linewidth=2.7, marker='o', markersize=5, label='新房同比中位数', zorder=5)
        axes[0].plot(recent['date'], recent['second_house_yoy'], color=used_color,
                     linewidth=2.3, marker='o', markersize=4, label='二手房同比中位数', zorder=5)
        axes[0].axhline(0, color='#9AA0A6', linewidth=0.8, alpha=0.65, zorder=2)
        self.plotter.fmt_single(
            fig, axes[0], title='70城住宅价格（最近15个月）', ylabel='同比中位数(%)',
            rotation=20, data=[recent['new_house_yoy'], recent['second_house_yoy']],
        )
        self.plotter.set_no_margins(axes[0])

        self.plotter.fill_diverging_gradient(
            axes[1], frame['date'], frame['second_house_yoy'], baseline=0,
            positive_color='#C95A55', negative_color='#3D8B68', alpha_top=0.32, zorder=1,
        )
        axes[1].plot(frame['date'], frame['new_house_yoy'], color=new_color,
                     linewidth=1.7, label='新房同比中位数', zorder=5)
        axes[1].plot(frame['date'], frame['second_house_yoy'], color=used_color,
                     linewidth=1.6, label='二手房同比中位数', zorder=5)
        axes[1].axhline(0, color='#9AA0A6', linewidth=0.8, alpha=0.65, zorder=2)
        self.plotter.fmt_single(
            fig, axes[1], title='历史走势（最近10年）', ylabel='同比中位数(%)',
            rotation=15, data=[frame['new_house_yoy'], frame['second_house_yoy']],
        )
        self.plotter.set_no_margins(axes[1])

        path = 'output/finance/real_estate.png'
        self.plotter.save(fig, path)
        return path
