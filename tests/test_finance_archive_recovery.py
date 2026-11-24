import logging
import sqlite3
from types import SimpleNamespace

import pandas as pd
import pytest

from core.data_archive import DataArchive
from sources.finance.manager import DataManager


class CheckpointClient:
    def __init__(self):
        self.connection = sqlite3.connect(':memory:')

    def query(self, sql, params=None):
        cursor = self.connection.execute(sql, params or [])
        rows = [dict(zip([item[0] for item in cursor.description], row)) for row in cursor.fetchall()] if cursor.description else []
        return {'success': True, 'data': [{'results': rows}]}


def manager(monkeypatch):
    value = object.__new__(DataManager)
    value.logger = logging.getLogger('test.finance.archive')
    value.tags = {'pmi': {'date': '2026-11-01', 'url': 'https://assets.test/finance/pmi/latest.png'}}
    value.d1_client = CheckpointClient()
    state = {'calls': 0, 'fail': True}

    def store(**kwargs):
        state['calls'] += 1
        assert kwargs['require_complete'] is True
        if state['fail']:
            raise RuntimeError('injected archive failure')
        return 2

    value.archive = SimpleNamespace(store_dataframe=store)
    monkeypatch.setattr('sources.finance.manager.db.save_monitor_data', lambda *a, **kw: None)
    return value, state


def frame(value=50.2):
    return pd.DataFrame({'date': ['2026-11-01'], 'manufacture': [value], 'non_manufacture': [51.1]})


def test_cached_chart_does_not_hide_failed_archive_and_next_run_retries(monkeypatch):
    value, state = manager(monkeypatch)
    with pytest.raises(RuntimeError, match='injected'):
        value.check_update_needed('pmi', frame())
    assert value.d1_client.connection.execute('SELECT COUNT(*) FROM finance_archive_checkpoints').fetchone()[0] == 0
    state['fail'] = False
    assert value.check_update_needed('pmi', frame())[0] is True
    assert state['calls'] == 2
    assert value.check_update_needed('pmi', frame())[0] is False
    assert state['calls'] == 2


def test_force_refresh_repairs_archive_even_when_chart_date_is_unchanged(monkeypatch):
    value, state = manager(monkeypatch)
    state['fail'] = False
    value.check_update_needed('pmi', frame())
    value.check_update_needed('pmi', frame(), force=True)
    assert state['calls'] == 2


def test_same_date_source_revision_updates_archive_and_chart(monkeypatch):
    value, state = manager(monkeypatch)
    state['fail'] = False
    value.check_update_needed('pmi', frame())
    assert value.check_update_needed('pmi', frame(50.4))[0] is True
    assert state['calls'] == 2


def test_strict_archive_rejects_partial_observation_writes():
    class BrokenD1:
        enabled = True

        def query(self, sql, params=None):
            return {'success': 'INSERT INTO data_observations' not in sql, 'data': [{'results': []}], 'error': 'injected'}

    with pytest.raises(RuntimeError, match='incomplete'):
        DataArchive(BrokenD1()).store_dataframe(
            domain='finance', group_name='pmi', frame=frame(), metrics={'manufacture': {'unit': '%'}},
            label='PMI', source='test', frequency='monthly', require_complete=True,
        )
