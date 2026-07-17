import pandas as pd
import requests

from .base import BaseIndicator


class NEVSaleIndicator(BaseIndicator):
    """CPCA new-energy passenger-car retail sales and retail penetration."""

    SOURCE_URL = "http://data.cpcadata.com/api/chartlist"

    @staticmethod
    def _month_date(value) -> pd.Timestamp:
        text = str(value or "").strip().replace("月份", "").replace("月", "")
        if "-" not in text:
            return pd.NaT
        year, month = text.split("-", 1)
        return pd.to_datetime(f"{year}-{int(month):02d}-01", errors="coerce")

    @classmethod
    def _normalize(cls, payload) -> pd.DataFrame:
        if not isinstance(payload, list) or len(payload) < 3:
            return pd.DataFrame()
        sales_rows = []
        for row in payload[0].get("dataList", []):
            month_text = str(row.get("month") or row.get("月份") or "")
            month_digits = "".join(char for char in month_text if char.isdigit())
            if not month_digits:
                continue
            for key, values in row.items():
                if not str(key).endswith("年") or not isinstance(values, list) or len(values) < 3:
                    continue
                date = pd.to_datetime(f"{str(key)[:4]}-{int(month_digits):02d}-01", errors="coerce")
                sales_rows.append({"date": date, "nev_retail_sales": values[2]})

        share_rows = []
        for row in payload[2].get("dataList", []):
            date = cls._month_date(row.get("月份"))
            values = row.get("NEV")
            if isinstance(values, list) and len(values) >= 4:
                share_rows.append({"date": date, "nev_retail_share": values[3]})

        sales = pd.DataFrame(sales_rows)
        shares = pd.DataFrame(share_rows)
        if sales.empty or shares.empty:
            return pd.DataFrame()
        frame = sales.merge(shares, on="date", how="left")
        for column in ["nev_retail_sales", "nev_retail_share"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return (
            frame.dropna(subset=["date", "nev_retail_sales"])
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )

    def fetch_data(self) -> pd.DataFrame:
        response = requests.get(self.SOURCE_URL, params={"charttype": "6"}, timeout=30)
        response.raise_for_status()
        frame = self._normalize(response.json())
        if frame.empty:
            raise RuntimeError("CPCA NEV retail series returned no valid observations")
        return frame

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values("date").copy()
        recent = frame.tail(13)
        if recent.empty:
            raise RuntimeError("NEV retail series is empty")
        frame["year"] = frame["date"].dt.year
        frame["month"] = frame["date"].dt.month
        frame["nev_retail_ytd"] = frame.groupby("year")["nev_retail_sales"].cumsum()

        fig, axes = self.plotter.create_ratio_axes(ratios=[3, 1])
        sales_color = "#2d8b78"
        share_color = "#c94844"
        axes[0].bar(
            recent["date"], recent["nev_retail_sales"], width=20,
            color=sales_color, alpha=0.58, label="新能源乘用车零售"
        )
        right = axes[0].twinx()
        right.plot(
            recent["date"], recent["nev_retail_share"],
            color=share_color, marker="o", markersize=3.5, linewidth=1.8,
            label="新能源零售渗透率"
        )
        self.plotter.fmt_twinx(
            fig, axes[0], right, title="新能源乘用车（最近13个月）",
            ylabel_left="零售销量（万辆）", ylabel_right="零售渗透率（%）",
            rotation=25, data_left=recent["nev_retail_sales"],
            data_right=recent["nev_retail_share"]
        )
        self.plotter.set_no_margins(axes[0])

        for year, group in frame.groupby("year"):
            axes[1].plot(
                group["month"], group["nev_retail_ytd"], marker="o",
                markersize=3, linewidth=1.6, label=str(year)
            )
        axes[1].set_xticks(range(1, 13))
        self.plotter.fmt_single(
            fig, axes[1], title="年内累计零售销量对比",
            xlabel="月份", ylabel="万辆", rotation=0, data=frame["nev_retail_ytd"]
        )
        axes[1].set_xlim(1, 12)

        path = "output/finance/nev_sale.png"
        self.plotter.save(fig, path)
        return path
