from concurrent.futures import ThreadPoolExecutor, as_completed

import akshare as ak
import pandas as pd

from .base import BaseIndicator
from .margin import MarginIndicator


SW1_INDUSTRIES = {
    "801010": "农林牧渔", "801030": "基础化工", "801040": "钢铁", "801050": "有色金属",
    "801080": "电子", "801110": "家用电器", "801120": "食品饮料", "801130": "纺织服饰",
    "801140": "轻工制造", "801150": "医药生物", "801160": "公用事业", "801170": "交通运输",
    "801180": "房地产", "801200": "商贸零售", "801210": "社会服务", "801230": "综合",
    "801710": "建筑材料", "801720": "建筑装饰", "801730": "电力设备", "801740": "国防军工",
    "801750": "计算机", "801760": "传媒", "801770": "通信", "801780": "银行",
    "801790": "非银金融", "801880": "汽车", "801890": "机械设备", "801950": "煤炭",
    "801960": "石油石化", "801970": "环保", "801980": "美容护理",
}


class MarketReviewIndicator(BaseIndicator):
    """中慢周期复盘数据；全部指标由公开观测值直接计算，不使用还原或占位序列。"""

    def _fetch_valuation(self) -> pd.DataFrame:
        raw = ak.stock_index_pe_lg(symbol="沪深300")
        required = {"日期", "指数", "滚动市盈率", "滚动市盈率中位数"}
        if raw is None or raw.empty or not required.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[["日期", "指数", "滚动市盈率", "滚动市盈率中位数"]].rename(columns={
            "日期": "date", "指数": "csi300_close", "滚动市盈率": "weighted_pe",
            "滚动市盈率中位数": "median_pe",
        })
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        for column in ["csi300_close", "weighted_pe", "median_pe"]:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        return frame.dropna(subset=["date", "weighted_pe", "median_pe"]).drop_duplicates("date", keep="last").sort_values("date")

    def _fetch_bond(self) -> pd.DataFrame:
        raw = ak.bond_zh_us_rate()
        if raw is None or raw.empty or not {"日期", "中国国债收益率10年"}.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[["日期", "中国国债收益率10年"]].rename(columns={"日期": "date", "中国国债收益率10年": "bond_10y"})
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
        frame["bond_10y"] = pd.to_numeric(frame["bond_10y"], errors="coerce")
        return frame.dropna().drop_duplicates("date", keep="last").sort_values("date")

    @staticmethod
    def _parse_market_month(value):
        matched = pd.Series([str(value)]).str.extract(r"(\d{4})年(\d{1,2})月份").iloc[0]
        if matched.isna().any():
            return pd.NaT
        return pd.Timestamp(year=int(matched.iloc[0]), month=int(matched.iloc[1]), day=1) + pd.offsets.MonthEnd(0)

    def _fetch_market_totals(self) -> pd.DataFrame:
        raw = ak.macro_china_stock_market_cap()
        required = {"数据日期", "市价总值-上海", "市价总值-深圳", "成交金额-上海", "成交金额-深圳"}
        if raw is None or raw.empty or not required.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[list(required)].copy()
        frame["date"] = frame["数据日期"].map(self._parse_market_month)
        for column in required - {"数据日期"}:
            frame[column] = pd.to_numeric(frame[column], errors="coerce")
        frame["total_market_cap"] = frame["市价总值-上海"] + frame["市价总值-深圳"]
        frame["monthly_turnover"] = frame["成交金额-上海"] + frame["成交金额-深圳"]
        frame["crowding_ratio"] = frame["monthly_turnover"] / frame["total_market_cap"] * 100
        return frame[["date", "total_market_cap", "monthly_turnover", "crowding_ratio"]].dropna(subset=["date", "total_market_cap"]).query("total_market_cap > 0").drop_duplicates("date", keep="last").sort_values("date")

    def _fetch_gdp_ttm(self) -> pd.DataFrame:
        raw = ak.macro_china_gdp()
        if raw is None or raw.empty or not {"季度", "国内生产总值-绝对值"}.issubset(raw.columns):
            return pd.DataFrame()
        frame = raw[["季度", "国内生产总值-绝对值"]].copy()
        parsed = frame["季度"].astype(str).str.extract(r"(\d{4})年第1(?:-(\d))?季度")
        frame["year"] = pd.to_numeric(parsed[0], errors="coerce")
        frame["quarter"] = pd.to_numeric(parsed[1].fillna(1), errors="coerce")
        frame["gdp_cumulative"] = pd.to_numeric(frame["国内生产总值-绝对值"], errors="coerce")
        frame = frame.dropna(subset=["year", "quarter", "gdp_cumulative"]).sort_values(["year", "quarter"])
        prior = frame.groupby("year")["gdp_cumulative"].shift(1).fillna(0)
        frame["gdp_single"] = frame["gdp_cumulative"] - prior
        frame["gdp_ttm"] = frame["gdp_single"].rolling(4, min_periods=4).sum()
        frame["date"] = pd.to_datetime(frame["year"].astype(int).astype(str) + "-" + (frame["quarter"].astype(int) * 3).astype(str) + "-01") + pd.offsets.MonthEnd(0)
        return frame[["date", "gdp_ttm"]].dropna().drop_duplicates("date", keep="last").sort_values("date")

    def _fetch_margin(self) -> pd.DataFrame:
        cached = self.manager.df_cache.get("margin")
        if isinstance(cached, pd.DataFrame) and not cached.empty:
            return cached[["date", "margin_balance"]].copy()
        fetched = MarginIndicator(self.manager, self.plotter).fetch_data()
        return fetched[["date", "margin_balance"]].copy() if isinstance(fetched, pd.DataFrame) and not fetched.empty else pd.DataFrame()

    @staticmethod
    def _one_year_industry_return(code: str):
        raw = ak.index_hist_sw(symbol=code, period="month")
        if raw is None or raw.empty or not {"日期", "收盘"}.issubset(raw.columns):
            return None
        frame = raw[["日期", "收盘"]].copy()
        frame["date"] = pd.to_datetime(frame["日期"], errors="coerce")
        frame["close"] = pd.to_numeric(frame["收盘"], errors="coerce")
        frame = frame.dropna().sort_values("date")
        if len(frame) < 2:
            return None
        latest = frame.iloc[-1]
        cutoff = latest["date"] - pd.DateOffset(years=1)
        prior = frame[frame["date"] <= cutoff].tail(1)
        if prior.empty:
            prior = frame.head(1)
        base = float(prior.iloc[0]["close"])
        if base <= 0:
            return None
        return (float(latest["close"]) / base - 1) * 100

    def _fetch_industry_returns(self) -> pd.DataFrame:
        values = {}
        with ThreadPoolExecutor(max_workers=6) as executor:
            jobs = {executor.submit(self._one_year_industry_return, code): code for code in SW1_INDUSTRIES}
            for future in as_completed(jobs):
                code = jobs[future]
                try:
                    value = future.result()
                except Exception as exc:
                    self.logger.warning("SW1 %s fetch failed: %s", code, exc)
                    continue
                if value is not None:
                    values[f"industry_{code}"] = value
        if not values:
            return pd.DataFrame()
        return pd.DataFrame([{**values, "date": pd.Timestamp.now().normalize()}])

    def fetch_data(self) -> pd.DataFrame:
        valuation = self._fetch_valuation()
        if valuation.empty:
            raise RuntimeError("沪深300估值序列不可用")

        bond = self._fetch_bond()
        if not bond.empty:
            # Keep the equity valuation calendar intact and pair each trading day
            # with the latest already-published bond observation (never look ahead).
            valuation = pd.merge_asof(
                valuation.sort_values("date"),
                bond.sort_values("date"),
                on="date",
                direction="backward",
                tolerance=pd.Timedelta(days=10),
            )
            valuation["equity_yield_spread"] = 100 / valuation["median_pe"] - valuation["bond_10y"]

        totals = self._fetch_market_totals()
        gdp = self._fetch_gdp_ttm()
        if not totals.empty and not gdp.empty:
            totals = pd.merge_asof(totals.sort_values("date"), gdp.sort_values("date"), on="date", direction="backward")
            totals["buffett_ratio"] = totals["total_market_cap"] / totals["gdp_ttm"] * 100

        margin = self._fetch_margin()
        if not totals.empty and not margin.empty:
            margin["date"] = pd.to_datetime(margin["date"], errors="coerce")
            margin_monthly = margin.dropna().set_index("date").resample("ME").last().reset_index()
            totals = totals.merge(margin_monthly, on="date", how="left")
            totals["margin_leverage"] = totals["margin_balance"] / totals["total_market_cap"] * 100

        frames = [valuation]
        if not totals.empty:
            frames.append(totals)
        industry = self._fetch_industry_returns()
        if not industry.empty:
            frames.append(industry)
        result = frames[0]
        for frame in frames[1:]:
            result = result.merge(frame, on="date", how="outer")
        return result.drop_duplicates("date", keep="last").sort_values("date").reset_index(drop=True)

    def plot(self, df: pd.DataFrame) -> str:
        # Plotter configures the non-interactive backend before indicators render.
        # Importing pyplot lazily avoids switching backends during module discovery.
        import matplotlib.pyplot as plt

        fig, axes = plt.subplots(2, 2, figsize=(12, 8), constrained_layout=True)
        recent = df.dropna(subset=["median_pe"]).tail(260)
        axes[0, 0].plot(recent["date"], recent["median_pe"], color="#2563eb", label="PE中位数")
        axes[0, 0].plot(recent["date"], recent["weighted_pe"], color="#d99a22", label="加权PE")
        axes[0, 0].set_title("沪深300估值")
        axes[0, 0].legend(frameon=False)

        erp = df.dropna(subset=["equity_yield_spread"]).tail(260)
        axes[0, 1].plot(erp["date"], erp["equity_yield_spread"], color="#0f9d74")
        axes[0, 1].axhline(0, color="#94a3b8", linewidth=0.8)
        axes[0, 1].set_title("估值收益率 - 10年国债")

        monthly = df.dropna(subset=["buffett_ratio"]).tail(60)
        axes[1, 0].plot(monthly["date"], monthly["buffett_ratio"], color="#7c5ce7", label="巴菲特指标")
        axes[1, 0].set_title("总市值 / GDP(TTM)")

        industries = [(SW1_INDUSTRIES[code], pd.to_numeric(df[f"industry_{code}"], errors="coerce").dropna().iloc[-1])
                      for code in SW1_INDUSTRIES if f"industry_{code}" in df and not pd.to_numeric(df[f"industry_{code}"], errors="coerce").dropna().empty]
        industries = sorted(industries, key=lambda item: item[1])
        axes[1, 1].barh([item[0] for item in industries], [item[1] for item in industries], color=["#dc6260" if item[1] >= 0 else "#40a77b" for item in industries])
        axes[1, 1].set_title("申万一级行业近一年涨跌幅")
        axes[1, 1].tick_params(axis="y", labelsize=7)
        for axis in axes.flat:
            axis.grid(True, axis="y", linestyle="--", alpha=0.25)
            axis.spines[["top", "right"]].set_visible(False)
        path = "output/finance/marketreview.png"
        self.plotter.save(fig, path)
        return path
