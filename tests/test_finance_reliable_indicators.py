import pandas as pd
import pytest

from sources.finance.indicators.electricity import ElectricityIndicator
from sources.finance.indicators.margin import MarginIndicator
from sources.finance.indicators.social_finance import SocialFinanceIndicator
from sources.finance.indicators.trade import TradeIndicator
from sources.finance.indicators.insurance import InsuranceIndicator
from sources.finance.indicators.nev_sale import NEVSaleIndicator
from sources.finance.indicators.oil import OilIndicator
from sources.finance.indicators.real_estate import RealEstateIndicator
from sources.finance.indicators.lpr import LPRIndicator


def test_social_finance_keeps_monthly_observations_without_interpolation():
    raw = pd.DataFrame({
        "月份": ["202601", "202603"],
        "社会融资规模增量": [1000, 3000],
        "其中-人民币贷款": [800, 2200],
    })

    normalized = SocialFinanceIndicator._normalize_frame(raw)

    assert normalized["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-01-31", "2026-03-31"]
    assert normalized["social_finance_increment"].tolist() == [1000, 3000]
    assert len(normalized) == 2


def test_social_finance_parses_pbc_cumulative_reports_and_derives_real_months():
    may_html = """
      <main>二、前五个月社会融资规模增量累计为17.48万亿元
      其中，对实体经济发放的人民币贷款增加9万亿元。三、广义货币增长</main>
    """
    june_html = """
      <main>二、上半年社会融资规模增量累计为20.84万亿元
      其中，对实体经济发放的人民币贷款增加10.76万亿元。三、广义货币增长</main>
    """
    rows = [
        SocialFinanceIndicator._parse_official_report("2026年5月金融统计数据报告", may_html),
        SocialFinanceIndicator._parse_official_report("2026年上半年金融统计数据报告", june_html),
    ]
    monthly = SocialFinanceIndicator._monthly_from_cumulative(rows)

    assert monthly["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-05-31", "2026-06-30"]
    assert monthly["social_finance_increment"].tolist() == [174800, 33600]
    assert monthly["rmb_loan_increment"].tolist() == [90000, 17600]


def test_social_finance_official_rows_override_stale_akshare_months(monkeypatch):
    raw = pd.DataFrame({
        "月份": ["202604", "202605"],
        "社会融资规模增量": [6245, 100],
        "其中-人民币贷款": [-4006, 50],
    })
    official = pd.DataFrame({
        "date": pd.to_datetime(["2026-05-31", "2026-06-30"]),
        "social_finance_increment": [20300, 33600],
        "rmb_loan_increment": [5000, 17600],
    })
    indicator = object.__new__(SocialFinanceIndicator)
    indicator.logger = __import__("logging").getLogger("test.socialfinance")
    monkeypatch.setattr("sources.finance.indicators.social_finance.ak.macro_china_shrzgm", lambda: raw)
    monkeypatch.setattr(SocialFinanceIndicator, "_fetch_pbc_latest_months", classmethod(lambda cls: official))

    frame = indicator.fetch_data()

    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-04-30", "2026-05-31", "2026-06-30"]
    assert frame["social_finance_increment"].tolist() == [6245, 20300, 33600]


def test_trade_uses_customs_monthly_amounts_and_converts_thousand_usd():
    raw = pd.DataFrame({
        "月份": ["2026年06月份"],
        "当月出口额-金额": [412_387_100],
        "当月出口额-同比增长": [27.0],
        "当月进口额-金额": [286_764_000],
        "当月进口额-同比增长": [36.0],
    })

    normalized = TradeIndicator._normalize_frame(raw)

    assert normalized.loc[0, "date"].strftime("%Y-%m-%d") == "2026-06-30"
    assert normalized.loc[0, "export_amount"] == pytest.approx(4123.871)
    assert normalized.loc[0, "import_amount"] == pytest.approx(2867.64)
    assert normalized.loc[0, "trade_balance"] == pytest.approx(1256.231)


def test_electricity_derives_monthly_value_only_from_consecutive_cumulative_points():
    raw = pd.DataFrame({
        "统计时间": ["2026.1", "2026.2", "2026.4"],
        "全社会用电量": [80_000_000, 165_000_000, 333_000_000],
        "全社会用电量同比": [4.0, 4.5, 5.4],
    })

    normalized = ElectricityIndicator._normalize_frame(raw)

    assert normalized.loc[0, "electricity_monthly"] == 8000
    assert normalized.loc[1, "electricity_monthly"] == 8500
    assert pd.isna(normalized.loc[2, "electricity_monthly"])


def test_electricity_marks_february_as_combined_when_january_is_not_published():
    raw = pd.DataFrame({
        "统计时间": ["2026.2", "2026.3"],
        "全社会用电量": [165_000_000, 250_000_000],
        "全社会用电量同比": [4.5, 5.0],
    })

    normalized = ElectricityIndicator._normalize_frame(raw)

    assert normalized["period_span"].tolist() == [2, 1]
    assert pd.isna(normalized.loc[0, "electricity_monthly"])
    assert normalized.loc[1, "electricity_monthly"] == 8500


def test_margin_combines_only_same_day_shanghai_and_shenzhen_values():
    sh = pd.DataFrame({
        "日期": ["2026-07-14", "2026-07-15"],
        "融资余额": [100_000_000_000, 101_000_000_000],
        "融资买入额": [10_000_000_000, 11_000_000_000],
    })
    sz = pd.DataFrame({
        "日期": ["2026-07-15", "2026-07-16"],
        "融资余额": [99_000_000_000, 98_000_000_000],
        "融资买入额": [9_000_000_000, 8_000_000_000],
    })

    normalized = MarginIndicator._combine(sh, sz)

    assert normalized["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-07-15"]
    assert normalized.loc[0, "margin_balance"] == 2000
    assert normalized.loc[0, "margin_buy"] == 200


def test_margin_discards_exchange_zero_placeholder():
    raw = pd.DataFrame({
        "日期": ["2026-07-14", "2026-07-15"],
        "融资余额": [0, 100_000_000_000],
        "融资买入额": [0, 10_000_000_000],
    })

    normalized = MarginIndicator._normalize_exchange(raw, "sh")

    assert normalized["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-07-15"]


def test_insurance_derives_monthly_value_without_cross_year_subtraction():
    raw = pd.DataFrame({
        "日期": ["2025-12-01", "2026-01-01", "2026-02-01"],
        "最新值": [1_200_000, 200_000, 350_000],
    })

    normalized = InsuranceIndicator._normalize(raw)

    assert pd.isna(normalized.iloc[0]["premium_monthly"])
    assert normalized["premium_monthly"].iloc[1:].tolist() == [20.0, 15.0]
    assert normalized.iloc[-1]["premium_cumulative"] == 35.0


def test_nev_uses_retail_sales_and_retail_penetration_fields():
    payload = [
        {"dataList": [{"month": "6月", "2026年": [148.1, 120.0, 100.6753, 20.0]}]},
        {"dataList": []},
        {"dataList": [{
            "月份": "2026-6月",
            "ICE": [87.5, 59.5, 37.1, 37.2],
            "NEV": [148.1, 100.6753, 62.9, 62.8],
        }]},
    ]

    normalized = NEVSaleIndicator._normalize(payload)

    assert normalized.iloc[0]["nev_retail_sales"] == 100.6753
    assert normalized.iloc[0]["nev_retail_share"] == 62.8


def test_oil_does_not_publish_future_effective_price(monkeypatch):
    raw = pd.DataFrame({
        "调整日期": ["2020-01-01", "2099-01-01"],
        "汽油价格": [8000, 9999],
        "柴油价格": [7000, 8888],
    })
    monkeypatch.setattr("sources.finance.indicators.oil.ak.energy_oil_hist", lambda: raw)

    frame = OilIndicator(None, None).fetch_data()

    assert frame["date"].dt.strftime("%Y-%m-%d").tolist() == ["2020-01-01"]
    assert frame.iloc[-1]["gasoline"] == 8000


def test_real_estate_aggregates_price_indexes_and_market_breadth():
    raw = pd.DataFrame({
        'REPORT_DATE': ['2026-06-01'] * 3,
        'CITY': ['A', 'B', 'C'],
        'FIRST_COMHOUSE_SAME': [98, 100, 102],
        'FIRST_COMHOUSE_SEQUENTIAL': [99.9, 100, 100.2],
        'SECOND_HOUSE_SAME': [95, 97, 99],
        'SECOND_HOUSE_SEQUENTIAL': [99.8, 100.1, 100.2],
    })

    frame = RealEstateIndicator._aggregate(raw)

    # The production collector requires at least 60 cities. Verify the summary
    # formula separately with a replicated 60-city fixture.
    replicated = pd.concat([
        raw.assign(CITY=raw['CITY'] + f'-{copy}') for copy in range(20)
    ])
    frame = RealEstateIndicator._aggregate(replicated)
    assert frame.iloc[0]['new_house_yoy'] == pytest.approx(0)
    assert frame.iloc[0]['second_house_yoy'] == pytest.approx(-3)
    assert frame.iloc[0]['new_house_rise_share'] == pytest.approx(100 / 3)
    assert frame.iloc[0]['second_house_rise_share'] == pytest.approx(200 / 3)


def test_lpr_tracks_one_and_five_year_duration_independently(monkeypatch):
    raw = pd.DataFrame({
        'TRADE_DATE': pd.date_range('2026-01-20', periods=4, freq='ME'),
        'LPR1Y': [3.0, 3.0, 3.0, 3.0],
        'LPR5Y': [3.5, 3.5, 3.4, 3.4],
        'RATE_1': [3.0] * 4,
        'RATE_2': [3.5] * 4,
    })
    monkeypatch.setattr('sources.finance.indicators.lpr.ak.macro_china_lpr', lambda: raw)

    frame = LPRIndicator(None, None).fetch_data()

    assert frame.iloc[-1]['lpr1y_unchanged_months'] == 4
    assert frame.iloc[-1]['lpr5y_unchanged_months'] == 2
