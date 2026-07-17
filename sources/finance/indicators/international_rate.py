import pandas as pd

from .base import BaseIndicator


class InternationalRateIndicator(BaseIndicator):
    """Comparable overseas operating rates from continuously updated series."""

    FRED_SERIES = {
        # Federal funds target range upper limit, daily.
        'usa': 'DFEDTARU',
        # ECB deposit facility rate, daily.
        'eur': 'ECBDFR',
        # Japan uncollateralized overnight call/interbank rate, monthly.
        'jpy': 'IRSTCI01JPM156N',
    }

    @staticmethod
    def _fred_series(series_id: str, metric: str) -> pd.DataFrame:
        url = f'https://fred.stlouisfed.org/graph/fredgraph.csv?id={series_id}'
        frame = pd.read_csv(url)
        if frame.empty or series_id not in frame.columns:
            raise RuntimeError(f'FRED {series_id} returned no observations')
        frame = frame.rename(columns={'observation_date': 'date', series_id: metric})
        frame['date'] = pd.to_datetime(frame['date'], errors='coerce')
        frame[metric] = pd.to_numeric(frame[metric], errors='coerce')
        frame = frame[['date', metric]].dropna().drop_duplicates('date', keep='last')
        # Daily policy series repeat unchanged values. Keep rate decisions plus
        # the most recent observation so charts stay light and source dates are
        # honest instead of being fabricated by forward filling.
        changed = frame[metric].ne(frame[metric].shift())
        return frame[changed | (frame.index == frame.index[-1])]

    def fetch_data(self) -> pd.DataFrame:
        series = [self._fred_series(series_id, metric)
                  for metric, series_id in self.FRED_SERIES.items()]

        cached_lpr = self.manager.df_cache.get('lpr') if self.manager is not None else None
        if cached_lpr is not None and {'date', 'lpr1y'}.issubset(cached_lpr.columns):
            china = cached_lpr[['date', 'lpr1y']].rename(columns={'lpr1y': 'cn'}).copy()
        else:
            import akshare as ak
            china = ak.macro_china_lpr()[['TRADE_DATE', 'LPR1Y']].rename(
                columns={'TRADE_DATE': 'date', 'LPR1Y': 'cn'}
            )
        china['date'] = pd.to_datetime(china['date'], errors='coerce')
        china['cn'] = pd.to_numeric(china['cn'], errors='coerce')
        series.append(china[['date', 'cn']].dropna().drop_duplicates('date', keep='last'))

        frame = series[0]
        for item in series[1:]:
            frame = frame.merge(item, on='date', how='outer')
        return frame.sort_values('date').reset_index(drop=True)

    def plot(self, df: pd.DataFrame) -> str:
        # Forward fill only in a plotting copy. The archived frame remains
        # sparse, preserving each central bank's real source date.
        frame = df.sort_values('date').copy()
        frame[['usa', 'eur', 'jpy', 'cn']] = frame[['usa', 'eur', 'jpy', 'cn']].ffill()
        frame = frame.dropna(subset=['usa'])
        latest_date = frame['date'].max()
        recent = frame[frame['date'] >= latest_date - pd.DateOffset(months=15)].copy()
        history = frame[frame['date'] >= latest_date - pd.DateOffset(years=20)].copy()

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        colors = {'usa': '#C95A55', 'eur': '#3976A8', 'jpy': '#8A63B8', 'cn': '#8A94A0'}
        labels = {
            'usa': 'Fed目标上限', 'eur': 'ECB存款便利',
            'jpy': '日本隔夜拆借', 'cn': '中国1Y LPR（参考）',
        }

        for metric in ('usa', 'eur', 'jpy', 'cn'):
            axes[0].step(
                recent['date'], recent[metric], where='post', color=colors[metric],
                linewidth=1.8 if metric == 'cn' else (3 if metric == 'usa' else 2.5),
                linestyle='--' if metric == 'cn' else '-', label=labels[metric], zorder=5,
            )
        self.plotter.fmt_single(
            fig, axes[0], title='主要央行与隔夜政策操作利率（最近15个月）',
            ylabel='利率(%)', rotation=15,
            data=[recent[column] for column in ('usa', 'eur', 'jpy', 'cn')],
        )
        self.plotter.set_no_margins(axes[0])

        baseline = min(float(history[column].min()) for column in ('usa', 'eur', 'jpy', 'cn'))
        baseline = min(0.0, baseline)
        self.plotter.fill_gradient(
            axes[1], history['date'], history['usa'], color=colors['usa'],
            alpha_top=0.22, baseline=baseline, zorder=1, step='post',
        )
        for metric in ('usa', 'eur', 'jpy', 'cn'):
            axes[1].step(
                history['date'], history[metric], where='post', color=colors[metric],
                linewidth=1.1 if metric == 'cn' else 1.5,
                linestyle='--' if metric == 'cn' else '-', label=labels[metric], zorder=5,
            )
        self.plotter.fmt_single(
            fig, axes[1], title='历史走势（最近20年）', ylabel='利率(%)', rotation=15,
            data=[history[column] for column in ('usa', 'eur', 'jpy', 'cn')],
        )
        self.plotter.set_no_margins(axes[1])

        path = 'output/finance/international_rate.png'
        self.plotter.save(fig, path)
        return path
