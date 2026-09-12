from scripts.claim_scheduled_job import D1RestClient, TABLE_NAME, claim, load_d1_env_file


class FakeD1Client:
    def __init__(self, responses, enabled=True):
        self.enabled = enabled
        self.responses = list(responses)
        self.calls = []

    def query(self, sql, params=None):
        self.calls.append((sql, params))
        return self.responses.pop(0)


def test_manual_run_is_not_claimed_or_blocked():
    client = FakeD1Client([])
    assert claim('paper', '', client) == (True, 'manual run')
    assert client.calls == []


def test_claim_inserts_one_unique_slot():
    client = FakeD1Client([
        {'success': True, 'data': [{'meta': {'changes': 0}}]},
        {'success': True, 'data': [{'meta': {'changes': 1}}]},
    ])
    claimed, _reason = claim('paper', '2026-09-12T11:30:00.000Z', client)
    assert claimed is True
    assert TABLE_NAME in client.calls[0][0]
    assert client.calls[1][1] == ['paper|2026-09-12T11:30:00.000Z', 'paper', '2026-09-12T11:30:00.000Z']


def test_existing_slot_is_skipped():
    client = FakeD1Client([
        {'success': True, 'data': [{'meta': {'changes': 0}}]},
        {'success': True, 'data': [{'meta': {'changes': 0}}]},
    ])
    claimed, reason = claim('rss_fetch', '2026-09-12T10:30:00.000Z', client)
    assert claimed is False
    assert reason == 'already claimed'


def test_d1_failure_is_fail_closed():
    client = FakeD1Client([], enabled=False)
    claimed, reason = claim('finance', '2026-09-12T12:00:00.000Z', client)
    assert claimed is False
    assert 'unavailable' in reason


def test_loads_only_d1_credentials_from_env_file(tmp_path, monkeypatch):
    env_file = tmp_path / '.env'
    env_file.write_text(
        "CLOUDFLARE_D1_ACCOUNT_ID=account\n"
        "CLOUDFLARE_D1_DATABASE_ID='database'\n"
        'CLOUDFLARE_D1_API_TOKEN="token"\n'
        "UNRELATED_SECRET=do-not-load\n",
        encoding='utf-8',
    )
    for name in ('CLOUDFLARE_D1_ACCOUNT_ID', 'CLOUDFLARE_D1_DATABASE_ID', 'CLOUDFLARE_D1_API_TOKEN', 'UNRELATED_SECRET'):
        monkeypatch.delenv(name, raising=False)
    load_d1_env_file(str(env_file))
    assert __import__('os').environ['CLOUDFLARE_D1_ACCOUNT_ID'] == 'account'
    assert __import__('os').environ['CLOUDFLARE_D1_DATABASE_ID'] == 'database'
    assert __import__('os').environ['CLOUDFLARE_D1_API_TOKEN'] == 'token'
    assert 'UNRELATED_SECRET' not in __import__('os').environ


def test_rest_client_is_disabled_without_all_credentials(monkeypatch):
    for name in ('CLOUDFLARE_D1_ACCOUNT_ID', 'CLOUDFLARE_D1_DATABASE_ID', 'CLOUDFLARE_D1_API_TOKEN'):
        monkeypatch.delenv(name, raising=False)
    assert D1RestClient().enabled is False
