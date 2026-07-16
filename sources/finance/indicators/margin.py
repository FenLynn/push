import time

import akshare as ak
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
                    return frame
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
        axes[0].plot(recent["date"], recent["margin_balance"], color=balance_color, linewidth=2, label="融资余额")
        right = axes[0].twinx()
        right.bar(recent["date"], recent["margin_buy"], color=buy_color, alpha=0.28, width=0.8, label="融资买入额")
        self.plotter.fmt_twinx(
            fig, axes[0], right, title="沪深两融（近60个交易日）",
            ylabel_left="融资余额（亿元）", ylabel_right="买入额（亿元）", rotation=25,
            data_left=recent["margin_balance"], data_right=recent["margin_buy"],
        )
        self.plotter.set_no_margins(axes[0])

        axes[1].plot(history["date"], history["margin_balance"], color=balance_color, linewidth=1.5)
        self.plotter.fmt_single(
            fig, axes[1], title="融资余额长期走势", ylabel="亿元",
            rotation=15, data=history["margin_balance"],
        )
        self.plotter.set_no_margins(axes[1])

        path = "output/finance/margin.png"
        self.plotter.save(fig, path)
        return path
