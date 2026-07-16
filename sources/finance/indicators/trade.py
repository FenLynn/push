import akshare as ak
import pandas as pd

from .base import BaseIndicator


class TradeIndicator(BaseIndicator):
    """海关月度进出口数据；原始金额为千美元，统一换算为亿美元。"""

    @staticmethod
    def _normalize_frame(raw: pd.DataFrame) -> pd.DataFrame:
        columns = {
            "月份": "month",
            "当月出口额-金额": "export_raw",
            "当月出口额-同比增长": "export_yoy",
            "当月进口额-金额": "import_raw",
            "当月进口额-同比增长": "import_yoy",
        }
        if raw is None or raw.empty or not set(columns).issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[list(columns)].rename(columns=columns).copy()
        month = frame["month"].astype(str).str.extract(r"(?P<year>\d{4})\D*(?P<month>\d{1,2})")
        frame["date"] = pd.to_datetime(
            month["year"] + "-" + month["month"].str.zfill(2) + "-01", errors="coerce"
        ) + pd.offsets.MonthEnd(0)
        for column in ["export_raw", "import_raw", "export_yoy", "import_yoy"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["export_amount"] = frame["export_raw"] / 100000.0
        frame["import_amount"] = frame["import_raw"] / 100000.0
        frame["trade_balance"] = frame["export_amount"] - frame["import_amount"]
        return (
            frame[["date", "export_yoy", "import_yoy", "trade_balance", "export_amount", "import_amount"]]
            .dropna(subset=["date", "export_amount", "import_amount"])
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )

    def fetch_data(self) -> pd.DataFrame:
        try:
            frame = self._normalize_frame(ak.macro_china_hgjck())
            return frame if not frame.empty else None
        except Exception as exc:
            self.logger.error("Trade fetch failed: %s", exc)
            return None

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values("date").copy()
        latest = frame["date"].max()
        recent = frame[frame["date"] >= latest - pd.DateOffset(months=18)]
        annual = (
            frame.set_index("date")[["export_amount", "import_amount"]]
            .resample("YE").sum(min_count=10).dropna().tail(12).reset_index()
        )

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        export_color = "#c94844"
        import_color = "#2f8b62"
        axes[0].plot(recent["date"], recent["export_yoy"], color=export_color, marker="o", markersize=3.5, label="出口同比")
        axes[0].plot(recent["date"], recent["import_yoy"], color=import_color, marker="o", markersize=3.5, label="进口同比")
        axes[0].axhline(0, color="#8a94a0", linewidth=0.8, alpha=0.55)
        self.plotter.fmt_single(
            fig, axes[0], title="进出口同比（近18个月）", ylabel="%",
            rotation=20, data=[recent["export_yoy"], recent["import_yoy"]],
        )
        self.plotter.set_no_margins(axes[0])

        axes[1].plot(annual["date"], annual["export_amount"], color=export_color, marker="o", markersize=3, label="年度出口")
        axes[1].plot(annual["date"], annual["import_amount"], color=import_color, marker="o", markersize=3, label="年度进口")
        self.plotter.fmt_single(
            fig, axes[1], title="年度进出口规模", ylabel="亿美元",
            rotation=0, data=[annual["export_amount"], annual["import_amount"]],
        )
        self.plotter.set_no_margins(axes[1])

        path = "output/finance/trade.png"
        self.plotter.save(fig, path)
        return path
