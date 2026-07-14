import json
import unittest
from unittest.mock import patch

from core.dashboard_snapshot import DashboardSnapshotExporter
from sources.estate.source import EstateSource
from sources.life.source import LifeSource


class FakeKVClient:
    enabled = True

    def __init__(self, values=None):
        self.values = values or {}

    def get(self, key):
        if key not in self.values:
            return {'success': False, 'error': 'not found'}
        return {'success': True, 'value': self.values[key]}


class DashboardSnapshotTests(unittest.TestCase):
    def test_load_parses_existing_snapshot(self):
        snapshot = {'module': 'life', 'payload': {'boxReal': [{'name': 'A'}]}}
        client = FakeKVClient({'dashboard:snapshot:life:latest': json.dumps(snapshot)})
        self.assertEqual(DashboardSnapshotExporter(client).load('life'), snapshot)

    @patch('sources.life.source.load_dashboard_snapshot')
    def test_life_reuses_recent_missing_list(self, load_snapshot):
        load_snapshot.return_value = {
            'generatedAt': '2026-07-15T00:00:00Z',
            'payload': {'boxYear': [{'name': 'A'}]},
        }
        source = LifeSource.__new__(LifeSource)
        data = {
            'box_real': [{'name': 'B'}],
            'box_year': [],
            'tv_list': [],
            'show_list': [],
            'douban_list': [],
            'douban_high_rate': [],
            'book_list': [],
        }
        with patch.object(source, '_snapshot_age_days', return_value=1):
            merged, status = source._reuse_recent_snapshot(data)
        self.assertEqual(merged['box_year'], [{'name': 'A'}])
        self.assertEqual(status['boxYear']['state'], 'cached')
        self.assertEqual(status['boxReal']['state'], 'fresh')

    @patch('sources.estate.source.load_dashboard_snapshot')
    def test_estate_retains_only_missing_city(self, load_snapshot):
        load_snapshot.return_value = {
            'generatedAt': '2026-07-15T00:00:00Z',
            'payload': {
                'date': '2026-07-14',
                'items': [
                    {'city': 'Chengdu', 'category': 'NewHome_Count', 'value': 10, 'unit': 'units'},
                    {'city': 'Xian', 'category': 'SecondHand_Count_Anjuke', 'value': 20, 'unit': 'units'},
                ],
            },
        }
        source = EstateSource.__new__(EstateSource)
        current = [{'city': 'Xian', 'category': 'SecondHand_Count_Anjuke', 'value': 30, 'unit': 'units'}]
        with patch.object(source, '_snapshot_age_days', return_value=1):
            merged = source._merge_recent_snapshot(current)
        self.assertEqual(len(merged), 2)
        self.assertEqual([item for item in merged if item['city'] == 'Xian'][0]['value'], 30)
        cached = [item for item in merged if item['city'] == 'Chengdu'][0]
        self.assertTrue(cached['stale'])
        self.assertEqual(cached['sourceDate'], '2026-07-14')


if __name__ == '__main__':
    unittest.main()
