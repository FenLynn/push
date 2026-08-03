import pandas as pd
import pytest

from sources.finance.official_series import (
    cumulative_to_period_values,
    fetch_nbs_portal_series,
    merge_official_frames,
    parse_nbs_population_history,
    parse_bis_sdmx_csv,
    parse_mof_fiscal_release,
    parse_mca_quarterly_table,
    period_end,
)
from sources.finance.indicators import structural_macro as macro


def test_period_end_preserves_annual_monthly_and_quarterly_semantics():
    assert period_end("2025") == pd.Timestamp("2025-12-31")
    assert period_end("2026-02") == pd.Timestamp("2026-02-28")
    assert period_end("1995-Q4") == pd.Timestamp("1995-12-31")


def test_nbs_population_history_reads_both_year_columns():
    payload = """
    <table>
      <tr><th>year</th><th>population</th><th>density</th><th>year</th><th>population</th><th>density</th></tr>
      %s
    </table>
    """ % "".join(
        f"<tr><td>{1949 + i}</td><td>{54167 + i * 100}</td><td>57</td>"
        f"<td>{1975 + i}</td><td>{92420 + i * 100}</td><td>97</td></tr>"
        for i in range(25)
    )
    frame = parse_nbs_population_history(payload)
    assert len(frame) == 50
    assert frame.iloc[0]["population"] == 54167
    assert frame.iloc[-1]["date"] == pd.Timestamp("1999-12-31")


def test_official_overlay_does_not_erase_unrelated_validated_fields():
    base = pd.DataFrame({
        "date": pd.to_datetime(["2025-12-31"]),
        "population": [140_000],
        "urban_population": [95_000],
    })
    overlay = pd.DataFrame({
        "date": pd.to_datetime(["2025-12-31"]),
        "population": [140_100],
    })

    frame = merge_official_frames(base, overlay)

    assert frame.iloc[0]["population"] == 140_100
    assert frame.iloc[0]["urban_population"] == 95_000


def test_parse_bis_sdmx_csv_uses_named_fields_and_sorts():
    payload = "TIME_PERIOD,OBS_VALUE,OBS_STATUS\n2025-Q2,95,A\n2025-Q1,92.7,A\n"
    frame = parse_bis_sdmx_csv(payload)
    assert frame["date"].tolist() == [pd.Timestamp("2025-03-31"), pd.Timestamp("2025-06-30")]
    assert frame["value"].tolist() == [92.7, 95.0]


def test_mca_excel_html_is_parsed_by_label_not_fixed_cell_position():
    payload = """
    <table>
      <tr><td>结 婚 登 记*</td><td>万对</td><td>676.3</td><td></td></tr>
      <tr><td>离婚登记*</td><td>万对</td><td>274.3</td><td></td></tr>
    </table>
    """
    assert parse_mca_quarterly_table(payload) == {
        "marriages_cumulative": 676.3,
        "divorces_cumulative": 274.3,
    }


def test_cumulative_values_are_differenced_without_splitting_missing_periods():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2025-02-28", "2025-03-31", "2025-06-30"]),
        "revenue_cumulative": [100, 165, 330],
    })
    result = cumulative_to_period_values(frame, ["revenue_cumulative"])
    assert result["revenue_period"].tolist() == [100, 65, 165]
    assert result["period_span"].tolist() == [2, 1, 3]


def test_fertility_sums_exact_age_bands_without_interpolation(monkeypatch):
    dates = pd.date_range("1960-12-31", "2023-12-31", freq="YE")
    age = pd.DataFrame({
        "date": dates,
        **{f"{start}-{start + 4} years": [10000 + start] * len(dates) for start in range(15, 50, 5)},
    })
    fertility = pd.DataFrame({
        "date": dates,
        "Fertility rate": [1.0] * len(dates),
    })
    births = pd.DataFrame({"date": dates, "Births": [10_000_000] * len(dates)})
    monkeypatch.setattr(
        macro,
        "fetch_owid_grapher",
        lambda slug: age if slug.startswith("female") else (births if slug.startswith("annual-number") else fertility),
    )

    frame = macro.FertilityIndicator(None, None).fetch_data()

    assert frame.iloc[0]["women_15_49"] == pytest.approx(sum(10000 + start for start in range(15, 50, 5)) / 10000)
    assert frame.iloc[0]["women_20_34"] == pytest.approx(sum(10000 + start for start in range(20, 35, 5)) / 10000)
    assert frame.iloc[-1]["total_fertility_rate"] == 1.0
    assert frame.iloc[-1]["birth_population_un_estimate"] == 1000


def test_population_combines_yearbook_bridge_and_current_without_interpolation(monkeypatch):
    monkeypatch.setattr(macro, "fetch_nbs_yearbook_rows", lambda _table: [
        [1949, 54167, 28145, 51.96, 26022, 48.04, 5765, 10.64, 48402, 89.36],
        *[[year, 100000 + year, 0, 0, 0, 0, 50000 + year, 50, 0, 0] for year in range(1950, 2012)],
    ])
    current = pd.DataFrame({
        "date": pd.to_datetime(["2016-12-31", "2017-12-31"]),
        "A030101": [139232, 140011], "A030104": [81924, 84343],
    })
    monkeypatch.setattr(macro, "fetch_dbnomics_dataset", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(macro, "fetch_nbs_population_history", lambda: pd.DataFrame())

    frame = macro.PopulationIndicator(None, None).fetch_data()

    assert frame.iloc[0]["date"] == pd.Timestamp("1949-12-31")
    assert frame.loc[frame["date"] == pd.Timestamp("2012-12-31"), "population"].item() == 135404
    assert frame.iloc[-1]["urbanization_rate"] == pytest.approx(84343 / 140011 * 100)
    assert not (frame["date"].dt.year == 2015.5).any()


def test_demography_two_year_columns_are_both_preserved(monkeypatch):
    monkeypatch.setattr(macro, "fetch_nbs_yearbook_rows", lambda _table: [
        [1978, 18.25, 6.25, 12.00, 1996, 16.98, 6.56, 10.42],
        *[[year, 12, 7, 5, 2000, 14, 7, 7] for year in range(1949, 1990)],
    ])
    current = pd.DataFrame({
        "date": pd.to_datetime(["2016-12-31"]),
        "A030201": [12.43], "A030202": [7.09], "A030203": [5.34],
    })
    monkeypatch.setattr(macro, "fetch_dbnomics_dataset", lambda *_args, **_kwargs: current)
    monkeypatch.setattr(macro, "fetch_nbs_portal_series", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(macro, "complete_population", lambda: pd.DataFrame({
        "date": pd.to_datetime(["2015-12-31", "2016-12-31"]),
        "population": [137462, 138271],
    }))

    frame = macro.DemographyIndicator(None, None).fetch_data()

    assert frame.loc[frame["date"] == pd.Timestamp("1978-12-31"), "birth_rate"].item() == 18.25
    assert frame.loc[frame["date"] == pd.Timestamp("1996-12-31"), "natural_growth_rate"].item() == 10.42
    latest = frame.loc[frame["date"] == pd.Timestamp("2016-12-31")].iloc[0]
    assert latest["birth_population"] == pytest.approx(((137462 + 138271) / 2) * 12.43 / 1000)


def test_marriage_preserves_annual_history_and_adds_quarterly_flows(monkeypatch):
    annual = pd.DataFrame({
        "date": pd.to_datetime(["2024-12-31"]),
        "A0P0C02": [610.6], "A0P0C03": [917.2], "A0P0C06": [262.1],
    })
    quarterly = pd.DataFrame({
        "date": pd.to_datetime(["2025-03-31"]),
        "marriages_cumulative": [181.0], "marriages_quarter": [181.0],
        "marriages_quarter_yoy": [-8.0], "divorces_cumulative": [64.0],
        "divorces_quarter": [64.0], "divorces_quarter_yoy": [2.0],
    })
    monkeypatch.setattr(macro, "fetch_dbnomics_dataset", lambda *_args, **_kwargs: annual)
    monkeypatch.setattr(macro, "fetch_nbs_portal_series", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(macro, "fetch_mca_quarterly_marriage", lambda: quarterly)
    frame = macro.MarriageIndicator(None, None).fetch_data()
    assert frame.loc[frame["date"] == pd.Timestamp("2024-12-31"), "marriages_annual"].item() == 610.6
    assert frame.loc[frame["date"] == pd.Timestamp("2025-03-31"), "marriages_quarter"].item() == 181.0


def test_tax_structure_uses_same_year_tax_total_as_denominator(monkeypatch):
    raw = pd.DataFrame({
        "date": pd.to_datetime(["2024-12-31"]),
        "A080601": [175000], "A080602": [70000], "A080604": [17500],
        "A080606": [14000], "A080607": [42000],
    })
    monkeypatch.setattr(macro, "fetch_dbnomics_dataset", lambda *_args, **_kwargs: raw)
    monkeypatch.setattr(macro, "fetch_nbs_portal_series", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(macro, "fetch_mof_fiscal_releases", lambda: pd.DataFrame())

    frame = macro.TaxStructureIndicator(None, None).fetch_data()

    assert frame.iloc[0]["vat_share"] == pytest.approx(40)
    assert frame.iloc[0]["corporate_tax_share"] == pytest.approx(24)


def test_unemployment_does_not_fill_missing_age_series(monkeypatch):
    raw = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-31", "2026-02-28"]),
        "A0E0101": [5.2, 5.3], "A0E0102": [5.1, 5.1],
        "A0E0105": [None, 16.1], "A0E0109": [7.2, 7.2], "A0E0110": [4.1, 4.2],
    })
    monkeypatch.setattr(macro, "fetch_dbnomics_dataset", lambda *_args, **_kwargs: raw)
    monkeypatch.setattr(macro, "fetch_nbs_portal_series", lambda *_args, **_kwargs: pd.DataFrame())

    frame = macro.UnemploymentIndicator(None, None).fetch_data()

    assert pd.isna(frame.iloc[0]["youth_rate"])
    assert frame.iloc[1]["youth_rate"] == 16.1


def test_monthly_fiscal_uses_single_period_flows_and_comparable_yoy(monkeypatch):
    revenue = pd.DataFrame({
        "date": pd.to_datetime(["2024-02-29", "2024-03-31", "2025-02-28", "2025-03-31"]),
        "A0C0102": [100, 160, 110, 176], "A0C0103": [1, 2, 10, 10],
    })
    expenditure = pd.DataFrame({
        "date": revenue["date"], "A0C0202": [120, 190, 132, 209], "A0C0203": [1, 2, 10, 10],
    })
    monkeypatch.setattr(
        macro,
        "fetch_dbnomics_dataset",
        lambda _provider, dataset, _codes: revenue if dataset == "M_A0C01" else expenditure,
    )
    monkeypatch.setattr(macro, "fetch_nbs_portal_series", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(macro, "fetch_mof_fiscal_releases", lambda: pd.DataFrame(columns=[
        "date", "revenue", "expenditure", "revenue_growth", "expenditure_growth",
    ]))
    frame = macro.FiscalMonthlyIndicator(None, None).fetch_data()
    march_2025 = frame.loc[frame["date"] == pd.Timestamp("2025-03-31")].iloc[0]
    assert march_2025["revenue_monthly"] == 66
    assert march_2025["expenditure_monthly"] == 77
    assert march_2025["revenue_monthly_yoy"] == pytest.approx(10)
    assert march_2025["expenditure_monthly_yoy"] == pytest.approx(10)


def test_monthly_fiscal_drops_empty_january_before_marking_combined_release(monkeypatch):
    revenue = pd.DataFrame({
        "date": pd.to_datetime(["2026-01-31", "2026-02-28", "2026-03-31"]),
        "A0C0102": [None, 110, 176], "A0C0103": [None, 10, 10],
    })
    expenditure = pd.DataFrame({
        "date": revenue["date"], "A0C0202": [None, 132, 209], "A0C0203": [None, 10, 10],
    })
    monkeypatch.setattr(
        macro,
        "fetch_dbnomics_dataset",
        lambda _provider, dataset, _codes: revenue if dataset == "M_A0C01" else expenditure,
    )
    monkeypatch.setattr(macro, "fetch_nbs_portal_series", lambda *_args, **_kwargs: pd.DataFrame())
    monkeypatch.setattr(macro, "fetch_mof_fiscal_releases", lambda: pd.DataFrame())

    frame = macro.FiscalMonthlyIndicator(None, None).fetch_data()

    assert frame["date"].tolist() == [pd.Timestamp("2026-02-28"), pd.Timestamp("2026-03-31")]
    assert frame.iloc[0]["period_span"] == 2
    assert frame.iloc[0]["revenue_monthly"] == 110


def test_parse_mof_release_preserves_cumulative_period_and_growth_direction():
    payload = """
    <p>上半年，全国一般公共预算收入121047亿元，同比增长4.7%。</p>
    <p>其中，全国税收收入97865亿元，同比增长5.3%。</p>
    <p>1.国内增值税38581亿元，同比增长6%。</p>
    <p>2.国内消费税8673亿元，同比下降3.4%。</p>
    <p>3.企业所得税2 5 880亿元，同比增长3.9%。</p>
    <p>4.个人所得税8982亿元，同比增长1 3.1%。</p>
    <p>上半年，全国一般公共预算支出143329亿元，同比增长1.5%。</p>
    """
    record = parse_mof_fiscal_release("2026年上半年财政收支情况", payload, "https://example.test")
    assert record["date"] == pd.Timestamp("2026-06-30")
    assert record["revenue"] == 121047
    assert record["expenditure"] == 143329
    assert record["corporate_tax"] == 25880
    assert record["personal_tax"] == 8982
    assert record["revenue_growth"] == 4.7


def test_nbs_portal_resolves_labels_and_drops_empty_future_period(monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    listing = Response({"data": {"list": [
        {"_id": "u", "i_showname": "全国城镇调查失业率 (%)"},
        {"_id": "m", "i_showname": "31个大城市城镇调查失业率 (%)"},
    ]}})
    data = Response({"data": [
        {"code": "202607MM", "values": [{"_id": "u", "value": ""}, {"_id": "m", "value": ""}]},
        {"code": "202606MM", "values": [{"_id": "u", "value": "5.0"}, {"_id": "m", "value": "5.0"}]},
    ]})
    monkeypatch.setattr("sources.finance.official_series.requests.get", lambda *_args, **_kwargs: listing)
    monkeypatch.setattr("sources.finance.official_series.requests.post", lambda *_args, **_kwargs: data)
    frame = fetch_nbs_portal_series(
        "catalog",
        {"urban_rate": ("全国城镇调查失业率 (%)",), "major_city_rate": ("31个大城市城镇调查失业率 (%)",)},
        start="202601",
        end="202607",
    )
    assert frame["date"].tolist() == [pd.Timestamp("2026-06-30")]
    assert frame.iloc[0]["urban_rate"] == 5.0


def test_nbs_portal_parses_annual_periods(monkeypatch):
    class Response:
        def __init__(self, payload):
            self.payload = payload

        def raise_for_status(self):
            return None

        def json(self):
            return self.payload

    listing = Response({"data": {"list": [{"_id": "r", "i_showname": "一般公共预算收入 (亿元)"}]}})
    data = Response({"data": [{"code": "2025YY", "values": [{"_id": "r", "value": "216044.88"}]}]})
    monkeypatch.setattr("sources.finance.official_series.requests.get", lambda *_args, **_kwargs: listing)
    monkeypatch.setattr("sources.finance.official_series.requests.post", lambda *_args, **_kwargs: data)
    frame = fetch_nbs_portal_series(
        "catalog",
        {"revenue": ("一般公共预算收入 (亿元)",)},
        start="1950",
        end="2025",
        frequency="annual",
    )
    assert frame.iloc[0]["date"] == pd.Timestamp("2025-12-31")
    assert frame.iloc[0]["revenue"] == pytest.approx(216044.88)


def test_activity_indicator_aligns_three_monthly_sources(monkeypatch):
    monkeypatch.setattr(macro.ak, "macro_china_consumer_goods_retail", lambda: pd.DataFrame({
        "月份": ["2026年05月份", "2026年06月份"], "当月": [41090, 42690.7],
        "同比增长": [-0.6, 1.0], "累计": [206031.4, 248722.1], "累计-同比增长": [1.4, 1.3],
    }))
    monkeypatch.setattr(macro.ak, "macro_china_gyzjz", lambda: pd.DataFrame({
        "月份": ["2026年05月份", "2026年06月份"], "同比增长": [4.5, 5.3],
        "累计增长": [5.4, 5.4], "发布时间": ["", ""],
    }))
    monkeypatch.setattr(macro.ak, "macro_china_gdzctz", lambda: pd.DataFrame({
        "月份": ["2026年05月份", "2026年06月份"], "当月": [37219, 47858],
        "同比增长": [-17.15, -15.6], "环比增长": [-3.54, 28.58], "自年初累计": [178512, 226370],
    }))
    frame = macro.ActivityIndicator(None, None).fetch_data()
    assert frame["date"].tolist() == [pd.Timestamp("2026-05-31"), pd.Timestamp("2026-06-30")]
    assert frame.iloc[-1]["retail_sales_yoy"] == 1.0
    assert frame.iloc[-1]["industrial_yoy"] == 5.3
    assert frame.iloc[-1]["fixed_asset_investment"] == 47858
