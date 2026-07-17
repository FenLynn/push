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
        return frame[["date", "electricity_monthly", "electricity_cumulative_yoy"]].reset_index(drop=True)

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
        valid_monthly = frame.dropna(subset=["electricity_monthly"])
        latest = frame["date"].max()
        recent = frame[frame["date"] >= latest - pd.DateOffset(months=18)]
        frame["rolling_12m"] = frame["electricity_monthly"].rolling(12, min_periods=12).sum()

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        power_color = "#d49a22"
        yoy_color = "#3976a8"
        axes[0].bar(recent["date"], recent["electricity_monthly"], width=20, color=power_color, alpha=0.72, label="当月用电量")
        right = axes[0].twinx()
        right.plot(recent["date"], recent["electricity_cumulative_yoy"], color=yoy_color, marker="o", markersize=3.5, label="累计同比")
        self.plotter.fmt_twinx(
            fig, axes[0], right, title="全社会用电（近18个月）",
            ylabel_left="亿千瓦时", ylabel_right="%", rotation=20,
            data_left=recent["electricity_monthly"], data_right=recent["electricity_cumulative_yoy"],
        )
        self.plotter.set_no_margins(axes[0])

        history = frame.dropna(subset=["rolling_12m"])
        axes[1].plot(history["date"], history["rolling_12m"], color=power_color, linewidth=1.8)
        self.plotter.fmt_single(
            fig, axes[1], title="滚动12个月用电量", ylabel="亿千瓦时",
            rotation=20, data=history["rolling_12m"],
        )
        self.plotter.set_no_margins(axes[1])

        path = "output/finance/electricity.png"
        self.plotter.save(fig, path)
        return path
