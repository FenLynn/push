import re
import time
from urllib.parse import urljoin

import akshare as ak
import pandas as pd
import requests
from bs4 import BeautifulSoup

from .base import BaseIndicator


class SocialFinanceIndicator(BaseIndicator):
    """央行月度社会融资规模增量；不插值，不构造“存量”。"""

    PBC_LIST_URL = "https://www.pbc.gov.cn/diaochatongjisi/116219/116225/index.html"

    @staticmethod
    def _period_end_month(title: str) -> int | None:
        text = str(title or "")
        matched = re.search(r"年(\d{1,2})月金融统计数据报告", text)
        if matched:
            month = int(matched.group(1))
            return month if 1 <= month <= 12 else None
        aliases = {
            "一季度金融统计数据报告": 3,
            "上半年金融统计数据报告": 6,
            "前三季度金融统计数据报告": 9,
            "全年金融统计数据报告": 12,
        }
        return next((month for marker, month in aliases.items() if marker in text), None)

    @staticmethod
    def _amount_to_yi(value: str, unit: str) -> float:
        number = float(value)
        return number * 10000 if unit == "万亿元" else number

    @classmethod
    def _parse_official_report(cls, title: str, html: str) -> dict | None:
        year_match = re.search(r"(20\d{2})年", str(title or ""))
        month = cls._period_end_month(title)
        if not year_match or not month:
            return None
        soup = BeautifulSoup(html or "", "html.parser")
        text = " ".join(soup.get_text(" ", strip=True).split())
        section_start = text.find("二、")
        section_end = text.find("三、", section_start + 2)
        section = text[section_start:section_end if section_end > section_start else None]
        total_match = re.search(
            r"社会融资规模增量(?:累计)?为\s*([0-9.]+)\s*(万亿元|亿元)", section
        )
        loan_match = re.search(
            r"对实体经济发放的人民币贷款增加\s*([0-9.]+)\s*(万亿元|亿元)", section
        )
        if not total_match or not loan_match:
            return None
        return {
            "year": int(year_match.group(1)),
            "month": month,
            "social_finance_cumulative": cls._amount_to_yi(*total_match.groups()),
            "rmb_loan_cumulative": cls._amount_to_yi(*loan_match.groups()),
        }

    @classmethod
    def _monthly_from_cumulative(cls, rows: list[dict]) -> pd.DataFrame:
        frame = pd.DataFrame(rows)
        if frame.empty:
            return pd.DataFrame()
        frame = (
            frame.drop_duplicates(["year", "month"], keep="last")
            .sort_values(["year", "month"])
            .reset_index(drop=True)
        )
        frame["date"] = pd.to_datetime(
            frame["year"].astype(str) + "-" + frame["month"].astype(str).str.zfill(2) + "-01"
        ) + pd.offsets.MonthEnd(0)
        same_year = frame["year"].eq(frame["year"].shift())
        frame["social_finance_increment"] = frame["social_finance_cumulative"].diff().where(
            same_year, frame["social_finance_cumulative"]
        )
        frame["rmb_loan_increment"] = frame["rmb_loan_cumulative"].diff().where(
            same_year, frame["rmb_loan_cumulative"]
        )
        return frame[["date", "social_finance_increment", "rmb_loan_increment"]]

    @classmethod
    def _fetch_pbc_latest_months(cls) -> pd.DataFrame:
        headers = {"User-Agent": "Mozilla/5.0 (compatible; PushFinance/1.0)"}
        listing = requests.get(cls.PBC_LIST_URL, headers=headers, timeout=30)
        listing.raise_for_status()
        listing.encoding = "utf-8"
        soup = BeautifulSoup(listing.text, "html.parser")
        links = []
        for anchor in soup.find_all("a", href=True):
            title = " ".join(anchor.get_text(" ", strip=True).split())
            if re.search(r"20\d{2}年(?:\d{1,2}月|一季度|上半年|前三季度|全年)金融统计数据报告", title):
                links.append((title, urljoin(cls.PBC_LIST_URL, anchor["href"])))
        rows = []
        for title, url in dict(links).items():
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            response.encoding = "utf-8"
            parsed = cls._parse_official_report(title, response.text)
            if parsed:
                rows.append(parsed)
        return cls._monthly_from_cumulative(rows)

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
        base = pd.DataFrame()
        for attempt in range(3):
            try:
                base = self._normalize_frame(ak.macro_china_shrzgm())
                if not base.empty:
                    break
            except Exception as exc:
                self.logger.warning("Social Finance fetch attempt %s failed: %s", attempt + 1, exc)
            if attempt < 2:
                time.sleep(1)
        try:
            official = self._fetch_pbc_latest_months()
        except Exception as exc:
            self.logger.warning("PBC social-finance supplement unavailable: %s", exc)
            official = pd.DataFrame()
        if base.empty and official.empty:
            return None
        return (
            pd.concat([base, official], ignore_index=True)
            .dropna(subset=["date", "social_finance_increment"])
            .drop_duplicates("date", keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )

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
