import akshare as ak
import pandas as pd
import time

from .base import BaseIndicator


class ElectricityIndicator(BaseIndicator):
    """全社会用电量；把年内累计值还原成月度值，缺月时保持空值。"""

    @staticmethod
    def _normalize_frame(raw: pd.DataFrame) -> pd.DataFrame:
        required = {"统计时间", "全社会用电量", "全社会用电量同比"}
        if raw is None or raw.empty or not required.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[list(required)].copy()
        month = frame["统计时间"].astype(str).str.extract(r"(?P<year>\d{4})\D+(?P<month>\d{1,2})")
        frame["year"] = pd.to_numeric(month["year"], errors="coerce")
        frame["month"] = pd.to_numeric(month["month"], errors="coerce")
        frame["date"] = pd.to_datetime(
            month["year"] + "-" + month["month"].str.zfill(2) + "-01", errors="coerce"
        ) + pd.offsets.MonthEnd(0)
        frame["cumulative"] = pd.to_numeric(frame["全社会用电量"], errors="coerce") / 10000.0
        frame["electricity_cumulative_yoy"] = pd.to_numeric(frame["全社会用电量同比"], errors="coerce")
        frame = frame.dropna(subset=["date", "cumulative"]).sort_values("date").drop_duplicates("date", keep="last")
        previous = frame.groupby("year")["cumulative"].shift(1)
        previous_month = frame.groupby("year")["month"].shift(1)
        frame["electricity_monthly"] = frame["cumulative"] - previous
        frame.loc[frame["month"] == 1, "electricity_monthly"] = frame.loc[frame["month"] == 1, "cumulative"]
        frame.loc[(frame["month"] > 1) & (previous_month != frame["month"] - 1), "electricity_monthly"] = pd.NA
        frame.loc[frame["electricity_monthly"] < 0, "electricity_monthly"] = pd.NA
        january_years = set(frame.loc[frame["month"].eq(1), "year"])
        frame["period_span"] = 1
        frame.loc[frame["month"].eq(2) & ~frame["year"].isin(january_years), "period_span"] = 2
        return frame[["date", "year", "month", "cumulative", "electricity_monthly",
                      "electricity_cumulative_yoy", "period_span"]].reset_index(drop=True)

    def fetch_data(self) -> pd.DataFrame:
        last_error = None
        for attempt in range(3):
            try:
                frame = self._normalize_frame(ak.macro_china_society_electricity())
                if not frame.empty:
                    return frame
                last_error = RuntimeError('electricity source returned no observations')
            except Exception as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
        self.logger.error("Electricity fetch failed after retries: %s", last_error)
        return None

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values("date").copy()
        frame["quarter"] = ((frame["month"] - 1) // 3 + 1).astype(int)
        quarter_end = frame[frame["month"].isin([3, 6, 9, 12])].copy()
        quarter_end["quarter_total"] = quarter_end.groupby("year")["cumulative"].diff()
        quarter_end.loc[quarter_end["quarter"] == 1, "quarter_total"] = quarter_end.loc[
            quarter_end["quarter"] == 1, "cumulative"
        ]
        quarters = quarter_end.dropna(subset=["quarter_total"]).tail(8).copy()
        annual = frame[frame["month"] == 12].tail(20).copy()
        annual["annual_yoy"] = annual["cumulative"].pct_change() * 100

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        power_color = "#3976A8"
        yoy_color = "#C95A55"
        self.plotter.gradient_bars(
            axes[0], quarters["date"], quarters["quarter_total"], width=45,
            color=power_color, label="季度用电量",
        )
        right = axes[0].twinx()
        right.plot(quarters["date"], quarters["electricity_cumulative_yoy"], color=yoy_color,
                   marker="o", markersize=5, linewidth=2, label="累计同比")
        self.plotter.fmt_twinx(
            fig, axes[0], right, title="全社会用电（近8个季度）",
            ylabel_left="亿千瓦时", ylabel_right="%", rotation=20,
            data_left=quarters["quarter_total"], data_right=quarters["electricity_cumulative_yoy"],
        )
        self.plotter.set_no_margins(axes[0])

        self.plotter.gradient_bars(
            axes[1], annual["date"], annual["cumulative"], width=180,
            color=power_color, label="年度用电量",
        )
        annual_right = axes[1].twinx()
        annual_right.plot(annual["date"], annual["annual_yoy"], color=yoy_color,
                          marker="o", linewidth=1.8, label="年度同比", zorder=3)
        self.plotter.fmt_twinx(
            fig, axes[1], annual_right, title="年度用电量与同比（20年）",
            ylabel_left="亿千瓦时", ylabel_right="同比(%)", rotation=20,
            data_left=annual["cumulative"], data_right=annual["annual_yoy"],
        )
        self.plotter.set_no_margins(axes[1])

        path = "output/finance/electricity.png"
        self.plotter.save(fig, path)
        return path
