"""Long-horizon population, labour and public-finance indicators.

No interpolation is used. Historical observations come from NBS yearbooks or
communiques; current NBS and BIS series are transported by DBnomics.
"""

from __future__ import annotations

import pandas as pd

from .base import BaseIndicator
from ..official_series import (
    fetch_bis_sdmx_series,
    fetch_dbnomics_dataset,
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
        rows = fetch_nbs_yearbook_rows("D0301C")
        return pd.DataFrame([
            {"date": pd.Timestamp(f"{int(row[0])}-12-31"), "population": row[1],
             "urban_population": row[6], "urbanization_rate": row[7]}
            for row in rows if len(row) >= 10 and 1949 <= row[0] <= 2011
        ])

    def fetch_data(self) -> pd.DataFrame:
        current = fetch_dbnomics_dataset("NBS", "A_A0301", ["A030101", "A030104"])
        current = current.rename(columns={"A030101": "population", "A030104": "urban_population"})
        current["urbanization_rate"] = current["urban_population"] / current["population"] * 100
        bridge = COMMUNIQUE_2012_2015[["date", "population", "urban_population"]].copy()
        bridge["urbanization_rate"] = bridge["urban_population"] / bridge["population"] * 100
        frame = merge_official_frames(self._historical(), bridge, current)
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
        bridge = COMMUNIQUE_2012_2015[["date", "birth_rate", "death_rate", "natural_growth_rate"]]
        frame = merge_official_frames(self._historical(), bridge, current)
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
        frame = age[["date", "women_15_49", "women_20_34"]].merge(fertility, on="date", how="outer")
        frame = frame.sort_values("date").dropna(how="all", subset=["women_15_49", "women_20_34", "total_fertility_rate"])
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
        frame = merge_official_frames(self._historical(), bridge,
                                       current[["date", "age_65_share", "gross_dependency_ratio", "old_dependency_ratio"]])
        if frame.empty or frame["age_65_share"].dropna().max() > 40:
            raise ValueError("ageing series failed plausibility validation")
        return frame


class MarriageIndicator(StructuralMacroIndicator):
    title = "结婚、初婚与离婚登记"
    primary = ("marriages", "first_marriages", "divorces")
    labels = {"marriages": "结婚登记", "first_marriages": "初婚人数", "divorces": "离婚登记"}

    def fetch_data(self) -> pd.DataFrame:
        frame = fetch_dbnomics_dataset("NBS", "A_A0P0C", ["A0P0C02", "A0P0C03", "A0P0C06"])
        frame = frame.rename(columns={"A0P0C02": "marriages", "A0P0C03": "first_marriages", "A0P0C06": "divorces"})
        frame = frame.dropna(how="all", subset=["marriages", "first_marriages", "divorces"])
        if frame.empty or (frame[["marriages", "first_marriages", "divorces"]].dropna() < 0).any().any():
            raise ValueError("marriage series failed plausibility validation")
        return frame


class UnemploymentIndicator(StructuralMacroIndicator):
    title = "城镇调查失业率"
    primary = ("urban_rate", "major_city_rate", "youth_rate", "age_25_29_rate", "age_30_59_rate")
    labels = {"urban_rate": "全国城镇", "major_city_rate": "31个大城市", "youth_rate": "16-24岁(不含在校生)",
              "age_25_29_rate": "25-29岁(不含在校生)", "age_30_59_rate": "30-59岁(不含在校生)"}

    def fetch_data(self) -> pd.DataFrame:
        frame = fetch_dbnomics_dataset("NBS", "M_A0E01", ["A0E0101", "A0E0102", "A0E0105", "A0E0109", "A0E0110"])
        frame = frame.rename(columns={"A0E0101": "urban_rate", "A0E0102": "major_city_rate",
                                      "A0E0105": "youth_rate", "A0E0109": "age_25_29_rate",
                                      "A0E0110": "age_30_59_rate"})
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
        if frame.empty or frame[["revenue", "expenditure"]].dropna().min().min() <= 0:
            raise ValueError("fiscal series failed plausibility validation")
        return frame


class FiscalMonthlyIndicator(FiscalIndicator):
    title = "月度累计财政收支"

    def fetch_data(self) -> pd.DataFrame:
        revenue = fetch_dbnomics_dataset("NBS", "M_A0C01", ["A0C0102", "A0C0103"]).rename(
            columns={"A0C0102": "revenue", "A0C0103": "revenue_growth"})
        expenditure = fetch_dbnomics_dataset("NBS", "M_A0C02", ["A0C0202", "A0C0203"]).rename(
            columns={"A0C0202": "expenditure", "A0C0203": "expenditure_growth"})
        frame = revenue.merge(expenditure, on="date", how="outer").sort_values("date")
        if frame.empty or frame[["revenue", "expenditure"]].dropna(how="all").min().min() <= 0:
            raise ValueError("monthly fiscal series failed plausibility validation")
        return frame


class TaxStructureIndicator(StructuralMacroIndicator):
    title = "主要税种占税收收入比重"
    primary = ("vat_share", "corporate_tax_share", "personal_tax_share", "consumption_tax_share")
    labels = {"vat_share": "国内增值税", "corporate_tax_share": "企业所得税",
              "personal_tax_share": "个人所得税", "consumption_tax_share": "国内消费税"}

    def fetch_data(self) -> pd.DataFrame:
        frame = fetch_dbnomics_dataset("NBS", "A_A0806", ["A080601", "A080602", "A080604", "A080606", "A080607"])
        frame = frame.rename(columns={"A080601": "tax_revenue", "A080602": "vat", "A080604": "consumption_tax",
                                      "A080606": "personal_tax", "A080607": "corporate_tax"})
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
