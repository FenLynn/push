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
        prior_year = frame["social_finance_increment"].shift(12)
        frame["social_finance_yoy"] = (
            (frame["social_finance_increment"] / prior_year - 1) * 100
        ).where(prior_year > 0)
        recent = frame.tail(15).copy()

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        total_color = "#3976a8"
        loan_color = "#C94F45"

        self.plotter.gradient_bars(
            axes[0], recent["date"], recent["social_finance_increment"], width=20,
            color=total_color, label="社融增量",
        )
        right = axes[0].twinx()
        right.plot(recent["date"], recent["social_finance_yoy"], color=loan_color,
                   marker="o", markersize=4, linewidth=2, label="社融同比")
        axes[0].axhline(0, color="#8a94a0", linewidth=0.8, alpha=0.5)
        self.plotter.fmt_twinx(
            fig, axes[0], right, title="社融月度增量（近15个月）",
            ylabel_left="亿元", ylabel_right="同比(%)",
            rotation=20, data_left=recent["social_finance_increment"],
            data_right=recent["social_finance_yoy"],
        )
        self.plotter.set_no_margins(axes[0])
        tick_rows = recent.iloc[::2]
        axes[0].set_xticks(tick_rows["date"])
        axes[0].set_xticklabels(tick_rows["date"].dt.strftime('%Y%m'))

        history = frame.tail(120).copy()
        self.plotter.gradient_bars(
            axes[1], history["date"], history["social_finance_increment"], width=20,
            color=total_color, label="单月社融",
        )
        history_right = axes[1].twinx()
        history_right.plot(history["date"], history["social_finance_yoy"], color=loan_color,
                           linewidth=1.7, label="同比", zorder=3)
        self.plotter.fmt_twinx(
            fig, axes[1], history_right, title="社融单月增量与同比（10年）",
            ylabel_left="亿元", ylabel_right="同比(%)", rotation=20,
            data_left=history["social_finance_increment"], data_right=history["social_finance_yoy"],
        )
        self.plotter.set_no_margins(axes[1])

        path = "output/finance/socialfinance.png"
        self.plotter.save(fig, path)
        return path
