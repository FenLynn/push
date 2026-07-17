import akshare as ak
import pandas as pd
from .base import BaseIndicator

class PigIndicator(BaseIndicator):
    """生猪价格指数"""
    
    def fetch_data(self) -> pd.DataFrame:
        try:
            weekly = ak.index_hog_spot_price().rename(columns={
                '日期': 'date', '指数': 'index', '成交均价': 'transaction_price'
            })
            weekly['date'] = pd.to_datetime(weekly['date'])
            weekly['index'] = pd.to_numeric(weekly['index'], errors='coerce')
            weekly['transaction_price'] = pd.to_numeric(weekly.get('transaction_price'), errors='coerce')
            weekly = weekly[['date', 'index', 'transaction_price']].dropna(subset=['index'])

            # Soozhu's year-trend endpoint supplies roughly 200 genuine daily
            # observations, considerably more than its 15-row quote endpoint.
            try:
                daily = ak.spot_hog_year_trend_soozhu().rename(columns={
                    '日期': 'date', '价格': 'daily_price'
                })
                daily['date'] = pd.to_datetime(daily['date'])
                daily['daily_price'] = pd.to_numeric(daily['daily_price'], errors='coerce')
                daily = daily[['date', 'daily_price']].dropna()
            except Exception as exc:
                self.logger.warning('Recent daily hog price unavailable: %s', exc)
                daily = pd.DataFrame(columns=['date', 'daily_price'])

            # DCE live-hog main continuous contract (LH0), converted from
            # yuan/tonne to yuan/kg so it can be compared with cash hogs.
            try:
                futures = ak.futures_zh_daily_sina(symbol='LH0').rename(
                    columns={'date': 'date', 'close': 'futures_price'}
                )
                futures['date'] = pd.to_datetime(futures['date'], errors='coerce')
                futures['futures_price'] = pd.to_numeric(
                    futures['futures_price'], errors='coerce'
                ) / 1000.0
                futures = futures[['date', 'futures_price']].dropna()
            except Exception as exc:
                self.logger.warning('DCE live-hog futures unavailable: %s', exc)
                futures = pd.DataFrame(columns=['date', 'futures_price'])

            frame = weekly.merge(daily, on='date', how='outer')
            return frame.merge(futures, on='date', how='outer').sort_values('date')
        except Exception as e:
            self.logger.error(f"Pig Fetch Error: {e}")
            raise e

    def plot(self, df: pd.DataFrame) -> str:
        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        
        # 1. Standardized 13-month window
        weekly = df.dropna(subset=['index']).copy()
        daily = df.dropna(subset=['daily_price']).copy()
        futures = df.dropna(subset=['futures_price']).copy()
        if daily.empty:
            daily = weekly.dropna(subset=['transaction_price']).tail(15).copy()
            daily['daily_price'] = daily['transaction_price']
        
        # History: show ~10 years (Daily data, so ~2500 rows)
        df_long = weekly.copy()
        
        color = '#3976A8'
        
        # --- Top: Recent ---
        ax_top = axes[0]
        latest_date = max(daily['date'].max(), futures['date'].max())
        daily_short = daily[daily['date'] >= latest_date - pd.DateOffset(months=12)]
        futures_short = futures[futures['date'] >= latest_date - pd.DateOffset(months=12)]
        ax_top.plot(daily_short['date'], daily_short['daily_price'], color=color, linewidth=2.5,
                    marker='o', markersize=3, label='全国生猪现货日价', zorder=5)
        ax_top.plot(futures_short['date'], futures_short['futures_price'], color='#C95A55',
                    linewidth=2, label='大商所生猪主连', zorder=5)
        self.plotter.draw_current_line(daily['daily_price'].iloc[-1], ax_top, color)
        
        self.plotter.fmt_single(fig, ax_top, title='生猪现货与期货（最近12个月）',
                               ylabel='元/公斤', rotation=15,
                               data=[daily_short['daily_price'], futures_short['futures_price']])
        self.plotter.set_no_margins(ax_top)
        
        # --- Bottom: History ---
        ax_bot = axes[1]
        baseline = df_long['index'].min() * 0.96
        self.plotter.fill_gradient(ax_bot, df_long['date'], df_long['index'],
                                   color=color, baseline=baseline, zorder=1)
        ax_bot.plot(df_long['date'], df_long['index'], color=color, linewidth=1.5, zorder=4)
        
        self.plotter.fmt_single(fig, ax_bot, title='生猪价格指数（2015年至今，周度）',
                               ylabel='指数', rotation=15, data=df_long['index'])
        self.plotter.set_no_margins(ax_bot)
        
        path = "output/finance/pig.png"
        self.plotter.save(fig, path)
        return path
