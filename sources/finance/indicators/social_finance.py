import time

import akshare as ak
import pandas as pd

from .base import BaseIndicator


class SocialFinanceIndicator(BaseIndicator):
    """央行月度社会融资规模增量；不插值，不构造“存量”。"""

    @staticmethod
    def _normalize_frame(raw: pd.DataFrame) -> pd.DataFrame:
        required = {"月份", "社会融资规模增量", "其中-人民币贷款"}
        if raw is None or raw.empty or not required.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw.loc[:, list(required)].copy()
        month = frame["月份"].astype(str).str.extract(r"(?P<year>\d{4})(?P<month>\d{2})")
        frame["date"] = pd.to_datetime(
            month["year"] + "-" + month["month"] + "-01", errors="coerce"
        ) + pd.offsets.MonthEnd(0)
        frame["social_finance_increment"] = pd.to_numeric(frame["社会融资规模增量"], errors="coerce")
        frame["rmb_loan_increment"] = pd.to_numeric(frame["其中-人民币贷款"], errors="coerce")
        return (
            frame[["date", "social_finance_increment", "rmb_loan_increment"]]
            .dropna(subset=["date", "social_finance_increment"])
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )

    def fetch_data(self) -> pd.DataFrame:
        for attempt in range(3):
            try:
                frame = self._normalize_frame(ak.macro_china_shrzgm())
                if not frame.empty:
                    return frame
            except Exception as exc:
                self.logger.warning("Social Finance fetch attempt %s failed: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(1)
        return None

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values("date").copy()
        latest = frame["date"].max()
        recent = frame[frame["date"] >= latest - pd.DateOffset(months=24)]
        frame["rolling_12m"] = frame["social_finance_increment"].rolling(12, min_periods=12).sum()

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        total_color = "#3976a8"
        loan_color = "#d88932"

        axes[0].bar(
            recent["date"], recent["social_finance_increment"], width=20,
            color=total_color, alpha=0.72, label="社融增量",
        )
        axes[0].plot(
            recent["date"], recent["rmb_loan_increment"], color=loan_color,
            marker="o", markersize=3.5, linewidth=1.8, label="人民币贷款增量",
        )
        axes[0].axhline(0, color="#8a94a0", linewidth=0.8, alpha=0.5)
        self.plotter.fmt_single(
            fig, axes[0], title="社融月度增量（近24个月）", ylabel="亿元",
            rotation=20, data=[recent["social_finance_increment"], recent["rmb_loan_increment"]],
        )
        self.plotter.set_no_margins(axes[0])

        history = frame.dropna(subset=["rolling_12m"])
        axes[1].plot(history["date"], history["rolling_12m"], color=total_color, linewidth=1.8)
        self.plotter.fmt_single(
            fig, axes[1], title="滚动12个月社融增量", ylabel="亿元",
            rotation=20, data=history["rolling_12m"],
        )
        self.plotter.set_no_margins(axes[1])

        path = "output/finance/socialfinance.png"
        self.plotter.save(fig, path)
        return path
