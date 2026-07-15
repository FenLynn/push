import pandas as pd

from core.data_archive import DataArchive
from core.image_upload import R2Uploader


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
