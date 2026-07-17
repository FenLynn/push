import time

import akshare as ak
import matplotlib.ticker as ticker
import pandas as pd

from .base import BaseIndicator


class MarginIndicator(BaseIndicator):
    """沪深两市融资数据；只有两市同日真实值才进入全市场序列。"""

    @staticmethod
    def _normalize_exchange(raw: pd.DataFrame, suffix: str) -> pd.DataFrame:
        required = {"日期", "融资余额", "融资买入额"}
        if raw is None or raw.empty or not required.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[["日期", "融资余额", "融资买入额"]].copy()
        frame["date"] = pd.to_datetime(frame["日期"], errors="coerce")
        frame[f"balance_{suffix}"] = pd.to_numeric(frame["融资余额"], errors="coerce")
        frame[f"buy_{suffix}"] = pd.to_numeric(frame["融资买入额"], errors="coerce")
        normalized = frame[["date", f"balance_{suffix}", f"buy_{suffix}"]].dropna()
        # Exchange feeds occasionally publish a same-day all-zero placeholder.
        # It is not a market observation and would halve the combined balance.
        normalized = normalized[normalized[f"balance_{suffix}"] > 0]
        return (
            normalized
            .drop_duplicates("date", keep="last")
            .sort_values("date")
        )

    @classmethod
    def _combine(cls, sh_raw: pd.DataFrame, sz_raw: pd.DataFrame) -> pd.DataFrame:
        sh = cls._normalize_exchange(sh_raw, "sh")
        sz = cls._normalize_exchange(sz_raw, "sz")
        if sh.empty or sz.empty:
            return pd.DataFrame()
        frame = pd.merge(sh, sz, on="date", how="inner", validate="one_to_one")
        frame["margin_balance"] = (frame["balance_sh"] + frame["balance_sz"]) / 1e8
        frame["margin_buy"] = (frame["buy_sh"] + frame["buy_sz"]) / 1e8
        return frame[["date", "margin_balance", "margin_buy"]].sort_values("date").reset_index(drop=True)

    def fetch_data(self) -> pd.DataFrame:
        for attempt in range(2):
            try:
                frame = self._combine(
                    ak.macro_china_market_margin_sh(),
                    ak.macro_china_market_margin_sz(),
                )
                if not frame.empty:
                    return self._with_sh_index(frame)
            except Exception as exc:
                self.logger.warning("Margin fetch attempt %s failed: %s", attempt + 1, exc)
            if attempt == 0:
                time.sleep(1)
        return None

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values("date").copy()
        recent = frame.tail(60)
        history = frame[frame["date"] >= frame["date"].max() - pd.DateOffset(years=10)]

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        balance_color = "#c94844"
        buy_color = "#3976a8"
        # Trading-day ordinal removes weekend/holiday gaps without inventing
        # observations. Date labels still show the underlying exchange date.
        recent = recent.reset_index(drop=True)
        recent_x = recent.index.to_numpy()
        axes[0].plot(recent_x, recent["margin_balance"], color=balance_color, linewidth=2, label="融资余额")
        right = axes[0].twinx()
        self.plotter.gradient_bars(
            right, recent_x, recent["margin_buy"], color=buy_color,
            alpha_top=0.62, alpha_bottom=0.08, width=0.72, label="融资买入额",
        )
        tick_step = max(1, len(recent) // 6)
        tick_positions = list(range(0, len(recent), tick_step))
        if tick_positions[-1] != len(recent) - 1:
            tick_positions.append(len(recent) - 1)
        axes[0].xaxis.set_major_locator(ticker.FixedLocator(tick_positions))
        axes[0].xaxis.set_major_formatter(ticker.FixedFormatter([
            recent.iloc[position]["date"].strftime("%m-%d") for position in tick_positions
        ]))
        self.plotter.fmt_twinx(
            fig, axes[0], right, title="沪深两融（近60个交易日）",
            ylabel_left="融资余额（亿元）", ylabel_right="买入额（亿元）", rotation=25,
            data_left=recent["margin_balance"], data_right=recent["margin_buy"],
        )
        axes[0].set_xlim(-0.6, len(recent) - 0.4)

        history = history.reset_index(drop=True)
        history_x = history.index.to_numpy()
        axes[1].plot(history_x, history["margin_balance"], color=balance_color,
                     linewidth=1.5, label="融资余额", zorder=4)
        history_right = axes[1].twinx()
        history_right.plot(history_x, history["sh_close"], color="#3976A8",
                           linewidth=1.3, alpha=0.82, label="上证指数", zorder=3)
        year_change = history["date"].dt.year.ne(history["date"].dt.year.shift())
        year_positions = history.index[year_change].tolist()
        axes[1].xaxis.set_major_locator(ticker.FixedLocator(year_positions))
        axes[1].xaxis.set_major_formatter(ticker.FixedFormatter([
            str(history.iloc[position]["date"].year) for position in year_positions
        ]))
        self.plotter.fmt_twinx(
            fig, axes[1], history_right, title="融资余额与上证指数（10年）",
            ylabel_left="融资余额（亿元）", ylabel_right="上证指数", rotation=15,
            data_left=history["margin_balance"], data_right=history["sh_close"],
        )
        axes[1].set_xlim(0, max(1, len(history) - 1))

        path = "output/finance/margin.png"
        self.plotter.save(fig, path)
        return path
    @staticmethod
    def _with_sh_index(frame: pd.DataFrame) -> pd.DataFrame:
        try:
            index = ak.stock_zh_index_daily(symbol="sh000001")[["date", "close"]].copy()
            index["date"] = pd.to_datetime(index["date"], errors="coerce")
            index["sh_close"] = pd.to_numeric(index["close"], errors="coerce")
            return frame.merge(index[["date", "sh_close"]].dropna(), on="date", how="left")
        except Exception:
            frame = frame.copy()
            frame["sh_close"] = pd.NA
            return frame
