import pandas as pd
import pytest

from sources.finance.indicators.electricity import ElectricityIndicator
from sources.finance.indicators.margin import MarginIndicator
from sources.finance.indicators.social_finance import SocialFinanceIndicator
from sources.finance.indicators.trade import TradeIndicator


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
