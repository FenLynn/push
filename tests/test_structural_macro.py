import pandas as pd
import pytest

from sources.finance.official_series import parse_bis_sdmx_csv, period_end
from sources.finance.indicators import structural_macro as macro


def test_period_end_preserves_annual_monthly_and_quarterly_semantics():
    assert period_end("2025") == pd.Timestamp("2025-12-31")
    assert period_end("2026-02") == pd.Timestamp("2026-02-28")
    assert period_end("1995-Q4") == pd.Timestamp("1995-12-31")


def test_parse_bis_sdmx_csv_uses_named_fields_and_sorts():
    payload = "TIME_PERIOD,OBS_VALUE,OBS_STATUS\n2025-Q2,95,A\n2025-Q1,92.7,A\n"
    frame = parse_bis_sdmx_csv(payload)
    assert frame["date"].tolist() == [pd.Timestamp("2025-03-31"), pd.Timestamp("2025-06-30")]
    assert frame["value"].tolist() == [92.7, 95.0]


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
    monkeypatch.setattr(macro, "fetch_owid_grapher", lambda slug: age if slug.startswith("female") else fertility)

    frame = macro.FertilityIndicator(None, None).fetch_data()

    assert frame.iloc[0]["women_15_49"] == pytest.approx(sum(10000 + start for start in range(15, 50, 5)) / 10000)
    assert frame.iloc[0]["women_20_34"] == pytest.approx(sum(10000 + start for start in range(20, 35, 5)) / 10000)
    assert frame.iloc[-1]["total_fertility_rate"] == 1.0


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

    frame = macro.DemographyIndicator(None, None).fetch_data()

    assert frame.loc[frame["date"] == pd.Timestamp("1978-12-31"), "birth_rate"].item() == 18.25
    assert frame.loc[frame["date"] == pd.Timestamp("1996-12-31"), "natural_growth_rate"].item() == 10.42


def test_tax_structure_uses_same_year_tax_total_as_denominator(monkeypatch):
    raw = pd.DataFrame({
        "date": pd.to_datetime(["2024-12-31"]),
        "A080601": [175000], "A080602": [70000], "A080604": [17500],
        "A080606": [14000], "A080607": [42000],
    })
    monkeypatch.setattr(macro, "fetch_dbnomics_dataset", lambda *_args, **_kwargs: raw)

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

    frame = macro.UnemploymentIndicator(None, None).fetch_data()

    assert pd.isna(frame.iloc[0]["youth_rate"])
    assert frame.iloc[1]["youth_rate"] == 16.1
