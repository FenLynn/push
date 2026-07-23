import pandas as pd

from core.data_archive import DataArchive
from core.image_upload import R2Uploader
from sources.finance.indicators.cpi import CPIIndicator
from sources.finance.archive_catalog import ARCHIVE_CATALOG


class FakeD1Client:
    enabled = True

    def __init__(self, system_logs_exists=False):
        self.calls = []
        self.system_logs_exists = system_logs_exists

    def query(self, sql, params=None):
        self.calls.append((" ".join(sql.split()), list(params or [])))
        if "sqlite_master" in sql and self.system_logs_exists:
            return {"success": True, "data": [{"results": [{"name": "system_logs"}]}]}
        return {"success": True, "data": [{"results": []}]}


def test_monthly_series_is_normalized_and_upserted():
    client = FakeD1Client()
    archive = DataArchive(client)
    frame = pd.DataFrame({
        "date": ["2026-05-01", "2026-06-01"],
        "value": [99.8, 99.7],
    })

    saved = archive.store_dataframe(
        domain="estate",
        group_name="city_price_index",
        frame=frame,
        metrics={"value": {"label": "成都二手房环比", "unit": "index"}},
        label="成都住宅价格",
        source="AkShare/NBS-70-city",
        frequency="monthly",
        location="Chengdu",
        quality="official",
    )

    assert saved == 2
    observation_call = next(call for call in client.calls if "INSERT INTO data_observations" in call[0])
    assert observation_call[1][0] == "estate.city_price_index.chengdu.value"
    assert observation_call[1][1:4] == ["2026-05-01", "monthly", 99.8]


def test_daily_series_keeps_daily_and_builds_monthly_resolution():
    client = FakeD1Client()
    archive = DataArchive(client)
    frame = pd.DataFrame({
        "date": pd.date_range("2026-05-01", periods=35, freq="D"),
        "rate": range(35),
    })

    saved = archive.store_dataframe(
        domain="finance",
        group_name="test_rate",
        frame=frame,
        metrics={"rate": {"label": "测试利率", "unit": "%"}},
        label="测试",
        source="unit-test",
        frequency="daily",
    )

    assert saved == 37
    params = [param for sql, values in client.calls if "INSERT INTO data_observations" in sql for param in values]
    assert "daily" in params
    assert "monthly" in params


def test_replace_observations_prunes_stale_source_dates_after_successful_write():
    client = FakeD1Client()
    archive = DataArchive(client)
    frame = pd.DataFrame({"date": ["2026-06-01"], "rate": [0.841]})

    saved = archive.store_dataframe(
        domain="finance",
        group_name="internationalrate",
        frame=frame,
        metrics={"rate": {"label": "Japan overnight", "unit": "%"}},
        label="International rates",
        source="FRED",
        frequency="event",
        replace_observations=True,
    )

    assert saved == 1
    cleanup = [call for call in client.calls if "DELETE FROM data_observations" in call[0]]
    assert len(cleanup) == 1
    assert cleanup[0][1][0] == "finance.internationalrate.all.rate"


def test_finance_catalog_exposes_native_web_chart_companions():
    assert ARCHIVE_CATALOG["lpr"]["replace_observations"] is True
    assert "cumulative" in ARCHIVE_CATALOG["electricity"]["metrics"]
    assert "premium_cumulative" in ARCHIVE_CATALOG["insurance"]["metrics"]
    assert "sh_close" in ARCHIVE_CATALOG["margin"]["metrics"]
    assert "sh_close" in ARCHIVE_CATALOG["marketpe"]["metrics"]
    assert "median_pe" in ARCHIVE_CATALOG["marketreview"]["metrics"]
    assert "buffett_ratio" in ARCHIVE_CATALOG["marketreview"]["metrics"]
    assert "industry_801010" in ARCHIVE_CATALOG["marketreview"]["metrics"]


def test_r2_legacy_aliases_and_public_url(monkeypatch):
    monkeypatch.delenv("CLOUDFLARE_R2_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_ACCOUNT_ID", raising=False)
    monkeypatch.delenv("CLOUDFLARE_AccountId", raising=False)
    monkeypatch.delenv("CLOUDFLARE_D1_ACCOUNT_ID", raising=False)
    monkeypatch.setenv("R2_ACCOUNT_ID", "account-123")
    monkeypatch.setenv("R2_ACCESS_KEY", "access")
    monkeypatch.setenv("R2_SECRET_KEY", "secret")
    monkeypatch.setenv("R2_BUCKET_NAME", "push-service")
    monkeypatch.setenv("PUSH_R2_PUBLIC_BASE_URL", "https://assets.example.test/root/")

    assert R2Uploader.has_credentials() is True
    assert R2Uploader.has_public_url() is True
    assert R2Uploader._resolve_account_id() == "account-123"
    assert R2Uploader._resolve_public_base_url() == "https://assets.example.test/root"
    assert R2Uploader.stable_object_name("output/finance/cpi.png") == "images/finance/cpi.png"


def test_retention_uses_existing_system_log_timestamp_column():
    client = FakeD1Client(system_logs_exists=True)
    DataArchive(client).run_retention()

    cleanup_sql = [sql for sql, _ in client.calls if "DELETE FROM system_logs" in sql]
    assert cleanup_sql == ["DELETE FROM system_logs WHERE created_at < ?"]


def test_cpi_uses_observation_months_from_nbs_frame():
    raw = pd.DataFrame({
        "月份": ["2026年06月份", "2026年05月份"],
        "全国-同比增长": [1.0, 1.2],
        "全国-环比增长": [-0.3, -0.1],
    })

    normalized = CPIIndicator._normalize_nbs_frame(raw)

    assert normalized["date"].dt.strftime("%Y-%m-%d").tolist() == ["2026-05-01", "2026-06-01"]
    assert normalized["cpi_y"].tolist() == [1.2, 1.0]
    assert normalized["cpi_m"].tolist() == [-0.1, -0.3]
