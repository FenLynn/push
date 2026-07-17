import akshare as ak
import pandas as pd

from .base import BaseIndicator


class InsuranceIndicator(BaseIndicator):
    """Monthly original-premium income derived from the published YTD series."""

    @staticmethod
    def _normalize(raw: pd.DataFrame) -> pd.DataFrame:
        if raw is None or raw.empty or len(raw.columns) < 2:
            return pd.DataFrame()
        frame = raw.iloc[:, :2].copy()
        frame.columns = ["date", "premium_cumulative_raw"]
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["premium_cumulative"] = pd.to_numeric(
            frame["premium_cumulative_raw"], errors="coerce"
        ) / 10000  # source unit: 万元; archive/display unit: 亿元
        frame = (
            frame.dropna(subset=["date", "premium_cumulative"])
            .query("premium_cumulative > 0")
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )
        same_year = frame["date"].dt.year.eq(frame["date"].shift().dt.year)
        frame["premium_monthly"] = frame["premium_cumulative"].diff().where(same_year)
        january = frame["date"].dt.month.eq(1)
        frame.loc[january, "premium_monthly"] = frame.loc[january, "premium_cumulative"]
        frame.loc[frame["premium_monthly"] < 0, "premium_monthly"] = pd.NA

        previous = frame[["date", "premium_cumulative"]].copy()
        previous["date"] = previous["date"] + pd.DateOffset(years=1)
        previous = previous.rename(columns={"premium_cumulative": "premium_previous_year"})
        frame = frame.merge(previous, on="date", how="left")
        frame["premium_cumulative_yoy"] = (
            frame["premium_cumulative"] / frame["premium_previous_year"] - 1
        ) * 100
        return frame[[
            "date", "premium_monthly", "premium_cumulative",
            "premium_cumulative_yoy"
        ]]

    def fetch_data(self) -> pd.DataFrame:
        frame = self._normalize(ak.macro_china_insurance_income())
        if frame.empty:
            raise RuntimeError("Insurance upstream returned no valid cumulative observations")
        return frame

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values("date").copy()
        recent = frame.dropna(subset=["premium_monthly"]).tail(13)
        annual = frame[frame["date"].dt.month.eq(12)].tail(20)
        if recent.empty or annual.empty:
            raise RuntimeError("Insurance series is too short for audited charts")

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        premium_color = "#3976a8"
        yoy_color = "#c94844"
        axes[0].bar(
            recent["date"], recent["premium_monthly"], width=20,
            color=premium_color, alpha=0.58, label="当月原保险保费"
        )
        right = axes[0].twinx()
        right.plot(
            recent["date"], recent["premium_cumulative_yoy"],
            color=yoy_color, marker="o", markersize=3.5, linewidth=1.8,
            label="累计同比"
        )
        self.plotter.fmt_twinx(
            fig, axes[0], right, title="保险保费（最近13个月）",
            ylabel_left="当月保费（亿元）", ylabel_right="累计同比（%）",
            rotation=25, data_left=recent["premium_monthly"],
            data_right=recent["premium_cumulative_yoy"]
        )
        self.plotter.set_no_margins(axes[0])

        axes[1].plot(
            annual["date"], annual["premium_cumulative"],
            color=premium_color, marker="o", markersize=3, linewidth=1.6
        )
        self.plotter.fmt_single(
            fig, axes[1], title="完整年度原保险保费收入",
            ylabel="亿元", rotation=15, data=annual["premium_cumulative"]
        )
        self.plotter.set_no_margins(axes[1])

        path = "output/finance/insurance.png"
        self.plotter.save(fig, path)
        return path
