"""Long-horizon population, labour and public-finance indicators.

No interpolation is used. Historical observations come from NBS yearbooks or
communiques; current NBS and BIS series are transported by DBnomics.
"""

from __future__ import annotations

import logging
import re

import akshare as ak
import pandas as pd
import requests

from .base import BaseIndicator
from ..official_series import (
    cumulative_to_period_values,
    fetch_bis_sdmx_series,
    fetch_dbnomics_dataset,
    fetch_mca_quarterly_marriage,
    fetch_mof_fiscal_releases,
    fetch_nbs_portal_series,
    fetch_nbs_population_history,
    fetch_nbs_yearbook_rows,
    fetch_owid_grapher,
    merge_official_frames,
)


COMMUNIQUE_2012_2015 = pd.DataFrame({
    "date": pd.to_datetime(["2012-12-31", "2013-12-31", "2014-12-31", "2015-12-31"]),
    "population": [135404, 136072, 136782, 137462],
    "urban_population": [71182, 73111, 74916, 77116],
    "birth_rate": [12.10, 12.08, 12.37, 12.07],
    "death_rate": [7.15, 7.16, 7.16, 7.11],
    "natural_growth_rate": [4.95, 4.92, 5.21, 4.96],
    "age_65_share": [9.4, 9.7, 10.1, 10.5],
})

LOGGER = logging.getLogger(__name__)


def _optional_official_overlay(fetcher, label: str) -> pd.DataFrame:
    """Keep the historical mirror usable during a temporary official-site outage."""
    try:
        return fetcher()
    except (requests.RequestException, ValueError, KeyError) as exc:
        LOGGER.warning("%s overlay unavailable; retaining validated history: %s", label, exc)
        return pd.DataFrame()


def historical_population() -> pd.DataFrame:
    rows = fetch_nbs_yearbook_rows("D0301C")
    return pd.DataFrame([
        {"date": pd.Timestamp(f"{int(row[0])}-12-31"), "population": row[1],
         "urban_population": row[6], "urbanization_rate": row[7]}
        for row in rows if len(row) >= 10 and 1949 <= row[0] <= 2011
    ])


def complete_population() -> pd.DataFrame:
    current = fetch_dbnomics_dataset("NBS", "A_A0301", ["A030101", "A030104"])
    current = current.rename(columns={"A030101": "population", "A030104": "urban_population"})
    current["urbanization_rate"] = current["urban_population"] / current["population"] * 100
    bridge = COMMUNIQUE_2012_2015[["date", "population", "urban_population"]].copy()
    bridge["urbanization_rate"] = bridge["urban_population"] / bridge["population"] * 100
    complete_total = _optional_official_overlay(fetch_nbs_population_history, "NBS population history")
    return merge_official_frames(historical_population(), complete_total, bridge, current)


class StructuralMacroIndicator(BaseIndicator):
    title = ""
    primary: tuple[str, ...] = ()
    secondary: tuple[str, ...] = ()
    labels: dict[str, str] = {}
    output_name = ""

    def plot(self, df: pd.DataFrame) -> str:
        frame = df.sort_values("date")
        fig, ax = self.plotter.create_single_ax()
        palette = ["#2477D4", "#D95C59", "#36A56E", "#E2A72E", "#7A61D1"]
        plotted = []
        for index, column in enumerate(self.primary):
            if column not in frame or not frame[column].notna().any():
                continue
            line, = ax.plot(frame["date"], frame[column], marker="o", markersize=3.5,
                            color=palette[index % len(palette)], label=self.labels.get(column, column), zorder=3)
            plotted.append(line)
        right = None
        if self.secondary:
            right = ax.twinx()
            for offset, column in enumerate(self.secondary, start=len(self.primary)):
                if column not in frame or not frame[column].notna().any():
                    continue
                line, = right.plot(frame["date"], frame[column], marker="o", markersize=3.5,
                                   color=palette[offset % len(palette)],
                                   label=self.labels.get(column, column), zorder=3)
                plotted.append(line)
        self.plotter._beautify(ax, [frame[column] for column in self.primary if column in frame])
        if right is not None:
            self.plotter._beautify(right, [frame[column] for column in self.secondary if column in frame])
            right.grid(False)
        ax.set_title(self.title, fontsize=14, weight="bold")
        ax.legend(plotted, [line.get_label() for line in plotted], loc="best", frameon=False, ncol=min(3, len(plotted)))
        self.plotter.set_no_margins(ax)
        path = f"output/finance/{self.output_name or self.name}.png"
        self.plotter.save(fig, path)
        return path


class PopulationIndicator(StructuralMacroIndicator):
    title = "中国人口总量与城镇化"
    primary = ("population",)
    secondary = ("urbanization_rate",)
    labels = {"population": "年末总人口", "urbanization_rate": "城镇化率"}

    @staticmethod
    def _historical() -> pd.DataFrame:
        return historical_population()

    def fetch_data(self) -> pd.DataFrame:
        frame = complete_population()
        if len(frame) < 50 or not frame["population"].between(50000, 160000).all():
            raise ValueError("population history failed coverage/plausibility validation")
        return frame


class DemographyIndicator(StructuralMacroIndicator):
    title = "人口出生、死亡与自然增长"
    primary = ("birth_rate", "death_rate", "natural_growth_rate")
    labels = {"birth_rate": "出生率", "death_rate": "死亡率", "natural_growth_rate": "自然增长率"}

    @staticmethod
    def _historical() -> pd.DataFrame:
        records = []
        for row in fetch_nbs_yearbook_rows("D0302C"):
            for offset in (0, 4):
                if len(row) >= offset + 4 and 1949 <= row[offset] <= 2011:
                    records.append({
                        "date": pd.Timestamp(f"{int(row[offset])}-12-31"),
                        "birth_rate": row[offset + 1], "death_rate": row[offset + 2],
                        "natural_growth_rate": row[offset + 3],
                    })
        return pd.DataFrame(records)

    def fetch_data(self) -> pd.DataFrame:
        current = fetch_dbnomics_dataset("NBS", "A_A0302", ["A030201", "A030202", "A030203"])
        current = current.rename(columns={"A030201": "birth_rate", "A030202": "death_rate",
                                          "A030203": "natural_growth_rate"})
        direct = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "ffed4267bba24830beea5991d4c9bcfc",
                {
                    "birth_rate": ("人口出生率 (‰)",),
                    "death_rate": ("人口死亡率 (‰)",),
                    "natural_growth_rate": ("人口自然增长率 (‰)",),
                },
                start="1949",
                frequency="annual",
            ),
            "NBS demography",
        )
        bridge = COMMUNIQUE_2012_2015[["date", "birth_rate", "death_rate", "natural_growth_rate"]]
        frame = merge_official_frames(self._historical(), bridge, current, direct)
        population = complete_population()[["date", "population"]]
        frame = frame.merge(population, on="date", how="left").sort_values("date")
        prior_population = frame["population"].shift(1)
        consecutive = frame["date"].dt.year.diff().eq(1)
        average_population = ((frame["population"] + prior_population) / 2).where(consecutive)
        frame["birth_population"] = average_population * frame["birth_rate"] / 1000
        frame["death_population"] = average_population * frame["death_rate"] / 1000
        if len(frame) < 40 or frame[["birth_rate", "death_rate"]].max().max() > 50:
            raise ValueError("demography history failed coverage/plausibility validation")
        return frame


class FertilityIndicator(StructuralMacroIndicator):
    title = "育龄妇女与总和生育率（UN估算）"
    primary = ("women_15_49", "women_20_34")
    secondary = ("total_fertility_rate",)
    labels = {
        "women_15_49": "15-49岁妇女",
        "women_20_34": "20-34岁妇女",
        "total_fertility_rate": "总和生育率",
    }

    def fetch_data(self) -> pd.DataFrame:
        age = fetch_owid_grapher("female-population-by-age-group")
        all_ages = [f"{start}-{start + 4} years" for start in range(15, 50, 5)]
        core_ages = [f"{start}-{start + 4} years" for start in range(20, 35, 5)]
        missing = set(all_ages) - set(age.columns)
        if missing:
            raise ValueError(f"UN WPP female age series missing fields: {sorted(missing)}")
        age["women_15_49"] = age[all_ages].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=len(all_ages)) / 10000
        age["women_20_34"] = age[core_ages].apply(pd.to_numeric, errors="coerce").sum(axis=1, min_count=len(core_ages)) / 10000

        fertility = fetch_owid_grapher("children-per-woman-un")
        if "Fertility rate" not in fertility:
            raise ValueError("UN WPP fertility response missing Fertility rate")
        fertility = fertility[["date", "Fertility rate"]].rename(columns={"Fertility rate": "total_fertility_rate"})
        births = fetch_owid_grapher("annual-number-of-births-by-world-region")
        if "Births" not in births:
            raise ValueError("UN WPP birth response missing Births")
        births = births[["date", "Births"]].rename(columns={"Births": "birth_population_un_estimate"})
        births["birth_population_un_estimate"] = births["birth_population_un_estimate"] / 10000
        frame = age[["date", "women_15_49", "women_20_34"]].merge(fertility, on="date", how="outer")
        frame = frame.merge(births, on="date", how="outer")
        frame = frame.sort_values("date").dropna(how="all", subset=[
            "women_15_49", "women_20_34", "total_fertility_rate", "birth_population_un_estimate",
        ])
        if len(frame) < 60 or frame["women_15_49"].dropna().min() <= 0:
            raise ValueError("fertility foundation series failed coverage/plausibility validation")
        if frame["total_fertility_rate"].dropna().max() > 10:
            raise ValueError("total fertility rate failed plausibility validation")
        return frame.reset_index(drop=True)


class AgeingIndicator(StructuralMacroIndicator):
    title = "人口老龄化与抚养负担"
    primary = ("age_65_share", "old_dependency_ratio", "gross_dependency_ratio")
    labels = {"age_65_share": "65岁及以上占比", "old_dependency_ratio": "老年抚养比",
              "gross_dependency_ratio": "总抚养比"}

    @staticmethod
    def _historical() -> pd.DataFrame:
        return pd.DataFrame([
            {"date": pd.Timestamp(f"{int(row[0])}-12-31"), "age_65_share": row[7],
             "gross_dependency_ratio": row[8], "old_dependency_ratio": row[10]}
            for row in fetch_nbs_yearbook_rows("D0303C") if len(row) >= 11 and 1949 <= row[0] <= 2011
        ])

    def fetch_data(self) -> pd.DataFrame:
        current = fetch_dbnomics_dataset("NBS", "A_A0303", ["A030301", "A030304", "A030305", "A030307"])
        current["age_65_share"] = current["A030304"] / current["A030301"] * 100
        current = current.rename(columns={"A030305": "gross_dependency_ratio", "A030307": "old_dependency_ratio"})
        bridge = COMMUNIQUE_2012_2015[["date", "age_65_share"]]
        direct = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "c7743eefda9d44b5ad2ab0b4f29ba969",
                {
                    "population": ("年末总人口 (万人)",),
                    "age_65_population": ("65岁及以上人口 (万人)",),
                    "gross_dependency_ratio": ("总抚养比 (%)",),
                    "old_dependency_ratio": ("老年抚养比 (%)",),
                },
                start="1949",
                frequency="annual",
            ),
            "NBS ageing",
        )
        if not direct.empty:
            direct["age_65_share"] = direct["age_65_population"] / direct["population"] * 100
        frame = merge_official_frames(
            self._historical(), bridge,
            current[["date", "age_65_share", "gross_dependency_ratio", "old_dependency_ratio"]],
            direct[["date", "age_65_share", "gross_dependency_ratio", "old_dependency_ratio"]]
            if not direct.empty else direct,
        )
        if frame.empty or frame["age_65_share"].dropna().max() > 40:
            raise ValueError("ageing series failed plausibility validation")
        return frame


class MarriageIndicator(StructuralMacroIndicator):
    title = "结婚、初婚与离婚登记"
    primary = ("marriages_quarter", "divorces_quarter")
    secondary = ("marriages_quarter_yoy",)
    labels = {"marriages_quarter": "单季结婚登记", "divorces_quarter": "单季离婚登记",
              "marriages_quarter_yoy": "结婚登记同比"}

    def fetch_data(self) -> pd.DataFrame:
        annual = fetch_dbnomics_dataset("NBS", "A_A0P0C", ["A0P0C02", "A0P0C03", "A0P0C06"])
        annual = annual.rename(columns={"A0P0C02": "marriages_annual", "A0P0C03": "first_marriages_annual",
                                        "A0P0C06": "divorces_annual"})
        direct_annual = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "903b12570f7b4d73b578945248019f8f",
                {
                    "marriages_annual": ("结婚登记 (万对)",),
                    "first_marriages_annual": ("结婚登记初婚人数 (万人)",),
                    "divorces_annual": ("离婚登记 (万对)",),
                },
                start="1950",
                frequency="annual",
            ),
            "NBS annual marriage",
        )
        annual = merge_official_frames(annual, direct_annual)
        quarterly = fetch_mca_quarterly_marriage()
        frame = annual.merge(quarterly.drop(columns=["source_url"], errors="ignore"), on="date", how="outer")
        frame = frame.sort_values("date").dropna(how="all", subset=[
            "marriages_annual", "first_marriages_annual", "divorces_annual",
            "marriages_cumulative", "marriages_quarter", "divorces_cumulative", "divorces_quarter",
        ])
        level_columns = [
            "marriages_annual", "first_marriages_annual", "divorces_annual",
            "marriages_cumulative", "marriages_quarter", "divorces_cumulative", "divorces_quarter",
        ]
        if frame.empty or (frame[level_columns].dropna(how="all") < 0).any().any():
            raise ValueError("marriage series failed plausibility validation")
        return frame


class UnemploymentIndicator(StructuralMacroIndicator):
    title = "城镇调查失业率"
    primary = ("urban_rate", "major_city_rate", "youth_rate", "age_25_29_rate", "age_30_59_rate")
    labels = {"urban_rate": "全国城镇", "major_city_rate": "31个大城市", "youth_rate": "16-24岁(不含在校生)",
              "age_25_29_rate": "25-29岁(不含在校生)", "age_30_59_rate": "30-59岁(不含在校生)"}

    def fetch_data(self) -> pd.DataFrame:
        mirror = fetch_dbnomics_dataset("NBS", "M_A0E01", ["A0E0101", "A0E0102", "A0E0105", "A0E0109", "A0E0110"])
        mirror = mirror.rename(columns={"A0E0101": "urban_rate", "A0E0102": "major_city_rate",
                                        "A0E0105": "youth_rate", "A0E0109": "age_25_29_rate",
                                        "A0E0110": "age_30_59_rate"})
        direct = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "ee3b7046b390415b9b7745e3d16f6052",
                {
                    "urban_rate": ("全国城镇调查失业率 (%)",),
                    "major_city_rate": ("31个大城市城镇调查失业率 (%)",),
                    "youth_rate": ("全国城镇16—24岁劳动力失业率(%)",),
                    "age_25_29_rate": ("全国城镇25—29岁劳动力失业率 (%)",),
                    "age_30_59_rate": ("全国城镇30—59岁劳动力失业率 (%)",),
                },
                start="201801",
            ),
            "NBS unemployment",
        )
        frame = merge_official_frames(mirror, direct)
        if frame.empty or frame.select_dtypes("number").max().max() > 40:
            raise ValueError("unemployment series failed plausibility validation")
        return frame


class LabourIndicator(StructuralMacroIndicator):
    title = "劳动供给"
    primary = ("active_population", "registered_unemployed")
    labels = {"active_population": "经济活动人口", "registered_unemployed": "城镇登记失业人数"}

    def fetch_data(self) -> pd.DataFrame:
        active = fetch_dbnomics_dataset("NBS", "A_A0401", ["A040101"]).rename(columns={"A040101": "active_population"})
        registered = fetch_dbnomics_dataset("NBS", "A_A040N", ["A040N01"]).rename(columns={"A040N01": "registered_unemployed"})
        direct_registered = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "19839dbd8e82481b9524f031c6d816c5",
                {"registered_unemployed": ("城镇登记失业人数 (万人)",)},
                start="1950",
                frequency="annual",
            ),
            "NBS registered unemployment",
        )
        registered = merge_official_frames(registered, direct_registered)
        frame = active.merge(registered, on="date", how="outer").sort_values("date")
        if frame.empty or frame["active_population"].dropna().min() < 50000:
            raise ValueError("labour series failed plausibility validation")
        return frame


class FiscalIndicator(StructuralMacroIndicator):
    title = "国家财政收支"
    primary = ("revenue", "expenditure")
    secondary = ("revenue_growth", "expenditure_growth")
    labels = {"revenue": "财政收入", "expenditure": "财政支出", "revenue_growth": "收入增速",
              "expenditure_growth": "支出增速"}

    def fetch_data(self) -> pd.DataFrame:
        frame = fetch_dbnomics_dataset("NBS", "A_A0801", ["A080101", "A080102", "A080103", "A080104"])
        frame = frame.rename(columns={"A080101": "revenue", "A080102": "expenditure",
                                      "A080103": "revenue_growth", "A080104": "expenditure_growth"})
        direct = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "9ab4eeaba2264792b296b6658b6472dc",
                {
                    "revenue": ("一般公共预算收入 (亿元)",),
                    "expenditure": ("一般公共预算支出 (亿元)",),
                    "revenue_growth": ("一般公共预算收入增长速度 (%)",),
                    "expenditure_growth": ("一般公共预算支出增长速度 (%)",),
                },
                start="1950",
                frequency="annual",
            ),
            "NBS annual fiscal",
        )
        frame = merge_official_frames(frame, direct)
        current = _optional_official_overlay(fetch_mof_fiscal_releases, "MOF fiscal")
        if not current.empty:
            current = current.loc[current["date"].dt.month.eq(12), [
                "date", "revenue", "expenditure", "revenue_growth", "expenditure_growth",
            ]]
            frame = merge_official_frames(frame, current)
        if frame.empty or frame[["revenue", "expenditure"]].dropna().min().min() <= 0:
            raise ValueError("fiscal series failed plausibility validation")
        return frame


class FiscalMonthlyIndicator(FiscalIndicator):
    title = "月度财政收支与同比"

    def fetch_data(self) -> pd.DataFrame:
        revenue = fetch_dbnomics_dataset("NBS", "M_A0C01", ["A0C0102", "A0C0103"]).rename(
            columns={"A0C0102": "revenue", "A0C0103": "revenue_growth"})
        expenditure = fetch_dbnomics_dataset("NBS", "M_A0C02", ["A0C0202", "A0C0203"]).rename(
            columns={"A0C0202": "expenditure", "A0C0203": "expenditure_growth"})
        frame = revenue.merge(expenditure, on="date", how="outer").sort_values("date")
        direct_revenue = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "0083b57bb6b44d4d964b87a89192344e",
                {
                    "revenue": ("国家财政收入累计值 (亿元)",),
                    "revenue_growth": ("国家财政收入累计增长 (%)",),
                },
                start="200001",
            ),
            "NBS monthly fiscal revenue",
        )
        direct_expenditure = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "37564a0046c14c059382e3ad26a0d94f",
                {
                    "expenditure": ("国家财政支出 (不含债务还本) 累计值 (亿元)",),
                    "expenditure_growth": ("国家财政支出 (不含债务还本) 累计增长 (%)",),
                },
                start="200001",
            ),
            "NBS monthly fiscal expenditure",
        )
        if not direct_revenue.empty or not direct_expenditure.empty:
            if direct_revenue.empty:
                direct = direct_expenditure
            elif direct_expenditure.empty:
                direct = direct_revenue
            else:
                direct = direct_revenue.merge(direct_expenditure, on="date", how="outer")
            frame = merge_official_frames(frame, direct)
        current = _optional_official_overlay(fetch_mof_fiscal_releases, "MOF fiscal").rename(columns={
            "revenue": "revenue_cumulative", "expenditure": "expenditure_cumulative",
        })
        frame = frame.rename(columns={"revenue": "revenue_cumulative", "expenditure": "expenditure_cumulative"})
        if not current.empty:
            frame = merge_official_frames(frame, current[[
                "date", "revenue_cumulative", "expenditure_cumulative", "revenue_growth", "expenditure_growth",
            ]])
        frame = frame.loc[
            frame[["revenue_cumulative", "expenditure_cumulative"]].notna().any(axis=1)
        ].copy()
        if frame.empty or frame[["revenue_cumulative", "expenditure_cumulative"]].dropna(how="all").min().min() <= 0:
            raise ValueError("monthly fiscal series failed plausibility validation")
        frame = cumulative_to_period_values(frame, ["revenue_cumulative", "expenditure_cumulative"])
        frame = frame.rename(columns={"revenue_period": "revenue_monthly", "expenditure_period": "expenditure_monthly"})
        for metric in ("revenue_monthly", "expenditure_monthly"):
            prior = frame[["date", "period_span", metric]].copy()
            prior["date"] = prior["date"] + pd.DateOffset(years=1)
            prior = prior.rename(columns={metric: f"_{metric}_prior", "period_span": f"_{metric}_span"})
            frame = frame.merge(prior, on="date", how="left")
            comparable = frame["period_span"].eq(frame.pop(f"_{metric}_span"))
            prior_value = frame.pop(f"_{metric}_prior").where(comparable)
            frame[f"{metric}_yoy"] = (frame[metric] / prior_value - 1) * 100
        return frame


class ActivityIndicator(StructuralMacroIndicator):
    """Monthly demand, production and investment using published NBS values."""

    title = "消费、工业与固定资产投资"
    primary = ("retail_sales", "fixed_asset_investment")
    secondary = ("retail_sales_yoy", "industrial_yoy", "fixed_asset_yoy")
    labels = {
        "retail_sales": "社会消费品零售额",
        "fixed_asset_investment": "固定资产投资当月值",
        "retail_sales_yoy": "社零同比",
        "industrial_yoy": "工业增加值同比",
        "fixed_asset_yoy": "固定资产投资同比",
    }

    @staticmethod
    def _month_end(value) -> pd.Timestamp:
        match = re.search(r"(20\d{2})年(\d{1,2})月", str(value or ""))
        if not match:
            return pd.NaT
        return pd.Timestamp(f"{match.group(1)}-{int(match.group(2)):02d}-01") + pd.offsets.MonthEnd(0)

    def fetch_data(self) -> pd.DataFrame:
        retail = ak.macro_china_consumer_goods_retail().rename(columns={
            "月份": "period", "当月": "retail_sales", "同比增长": "retail_sales_yoy",
            "累计": "retail_sales_cumulative", "累计-同比增长": "retail_sales_cumulative_yoy",
        })
        industrial = ak.macro_china_gyzjz().rename(columns={
            "月份": "period", "同比增长": "industrial_yoy", "累计增长": "industrial_cumulative_yoy",
        })
        investment = ak.macro_china_gdzctz().rename(columns={
            "月份": "period", "当月": "fixed_asset_investment", "同比增长": "fixed_asset_yoy",
            "自年初累计": "fixed_asset_cumulative",
        })
        frames = []
        for source, columns in (
            (retail, ["retail_sales", "retail_sales_yoy", "retail_sales_cumulative", "retail_sales_cumulative_yoy"]),
            (industrial, ["industrial_yoy", "industrial_cumulative_yoy"]),
            (investment, ["fixed_asset_investment", "fixed_asset_yoy", "fixed_asset_cumulative"]),
        ):
            source = source.copy()
            source["date"] = source["period"].map(self._month_end)
            for column in columns:
                source[column] = pd.to_numeric(source[column], errors="coerce")
            frames.append(source[["date", *columns]].dropna(subset=["date"]))
        frame = frames[0]
        for source in frames[1:]:
            frame = frame.merge(source, on="date", how="outer")
        frame = frame.sort_values("date").drop_duplicates("date", keep="last")
        january_years = set(frame.loc[frame["date"].dt.month.eq(1), "date"].dt.year)
        frame["period_span"] = 1
        combined = frame["date"].dt.month.eq(2) & ~frame["date"].dt.year.isin(january_years)
        frame.loc[combined, "period_span"] = 2
        if frame.empty or frame["retail_sales"].dropna().min() <= 0:
            raise ValueError("monthly activity series failed plausibility validation")
        return frame.reset_index(drop=True)


class TaxStructureIndicator(StructuralMacroIndicator):
    title = "主要税种占税收收入比重"
    primary = ("vat_share", "corporate_tax_share", "personal_tax_share", "consumption_tax_share")
    labels = {"vat_share": "国内增值税", "corporate_tax_share": "企业所得税",
              "personal_tax_share": "个人所得税", "consumption_tax_share": "国内消费税"}

    def fetch_data(self) -> pd.DataFrame:
        frame = fetch_dbnomics_dataset("NBS", "A_A0806", ["A080601", "A080602", "A080604", "A080606", "A080607"])
        frame = frame.rename(columns={"A080601": "tax_revenue", "A080602": "vat", "A080604": "consumption_tax",
                                      "A080606": "personal_tax", "A080607": "corporate_tax"})
        direct = _optional_official_overlay(
            lambda: fetch_nbs_portal_series(
                "f478a1d7c27a4015b6f9af06ce6f617c",
                {
                    "tax_revenue": ("国家税收收入 (亿元)",),
                    "vat": ("国家国内增值税 (亿元)",),
                    "consumption_tax": ("国家国内消费税 (亿元)",),
                    "corporate_tax": ("国家企业所得税 (亿元)",),
                    "personal_tax": ("国家个人所得税 (亿元)",),
                },
                start="1950",
                frequency="annual",
            ),
            "NBS annual tax structure",
        )
        frame = merge_official_frames(frame, direct)
        current = _optional_official_overlay(fetch_mof_fiscal_releases, "MOF tax structure")
        if not current.empty:
            current = current.loc[current["date"].dt.month.eq(12), [
                "date", "tax_revenue", "vat", "consumption_tax", "personal_tax", "corporate_tax",
            ]].dropna(subset=["tax_revenue"])
            frame = merge_official_frames(frame, current)
        for source, target in (("vat", "vat_share"), ("consumption_tax", "consumption_tax_share"),
                               ("personal_tax", "personal_tax_share"), ("corporate_tax", "corporate_tax_share")):
            frame[target] = frame[source] / frame["tax_revenue"] * 100
        shares = ["vat_share", "consumption_tax_share", "personal_tax_share", "corporate_tax_share"]
        if frame.empty or frame[shares].max().max() > 100:
            raise ValueError("tax structure failed plausibility validation")
        return frame[["date", "tax_revenue", *shares]]


class GovernmentDebtIndicator(StructuralMacroIndicator):
    title = "中国广义政府债务杠杆率"
    primary = ("government_debt_ratio",)
    labels = {"government_debt_ratio": "广义政府债务/GDP"}

    def fetch_data(self) -> pd.DataFrame:
        frame = fetch_bis_sdmx_series("WS_TC", "2.0", "Q.CN.G.A.N.770.A")
        frame = frame.rename(columns={"value": "government_debt_ratio"}).dropna()
        if len(frame) < 40 or not frame["government_debt_ratio"].between(0, 200).all():
            raise ValueError("government debt series failed coverage/plausibility validation")
        if (pd.Timestamp.today().normalize() - frame["date"].max()).days > 550:
            raise ValueError("government debt series is stale by more than 550 days")
        return frame
