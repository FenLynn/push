import json
import unittest
from unittest.mock import MagicMock, patch

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

    @patch('requests.get')
    def test_life_parses_maoyan_yearly_chart(self, requests_get):
        response = MagicMock()
        response.text = '<script>var props = {"data":{"data":{"list":[{"movieName":"A","boxInfo":"12.34亿","avgViewBoxDesc":"40","releaseInfo":"2026-01-01"}],"majorTitle":"chart"}}};</script>'
        response.raise_for_status.return_value = None
        requests_get.return_value = response
        source = LifeSource.__new__(LifeSource)

        items = source._get_maoyan_movie_yearly()

        self.assertEqual(items[0]['name'], 'A')
        self.assertEqual(items[0]['box'], '12.34')

    @patch('requests.get')
    def test_life_parses_maoyan_web_heat(self, requests_get):
        response = MagicMock()
        response.json.return_value = {
            'dataList': {
                'list': [{
                    'currHeatDesc': '6789.10',
                    'seriesInfo': {'name': 'Series A', 'platformDesc': 'Platform', 'releaseInfo': 'Day 3'},
                }],
            },
        }
        response.raise_for_status.return_value = None
        requests_get.return_value = response
        source = LifeSource.__new__(LifeSource)

        items = source._get_maoyan_web_heat(0)

        self.assertEqual(items[0]['name'], 'Series A')
        self.assertEqual(items[0]['hot'], '6789.10')
        self.assertEqual(items[0]['type'], 'Platform · Day 3')

    @patch('sources.estate.source.load_dashboard_snapshot')
    def test_estate_retains_only_missing_city(self, load_snapshot):
        load_snapshot.return_value = {
            'generatedAt': '2026-07-15T00:00:00Z',
            'payload': {
                'date': '2026-07-14',
                'items': [
                    {'city': 'Chengdu', 'category': 'NewHome_Count', 'value': 10, 'unit': 'units'},
                    {'city': 'Xian', 'category': 'PresalePermit_Count', 'value': 2, 'unit': 'permits'},
                    {'city': 'Xian', 'category': 'SecondHand_Count_Anjuke', 'value': 20, 'unit': 'units'},
                ],
            },
        }
        source = EstateSource.__new__(EstateSource)
        current = [{'city': 'Xian', 'category': 'PresalePermit_Count', 'value': 3, 'unit': 'permits'}]
        with patch.object(source, '_snapshot_age_days', return_value=1):
            merged = source._merge_recent_snapshot(current)
        self.assertEqual(len(merged), 2)
        self.assertEqual([item for item in merged if item['city'] == 'Xian'][0]['value'], 3)
        cached = [item for item in merged if item['city'] == 'Chengdu'][0]
        self.assertTrue(cached['stale'])
        self.assertEqual(cached['sourceDate'], '2026-07-14')

    @patch('sources.estate.source.requests.post')
    @patch('sources.estate.source.requests.get')
    @patch('sources.estate.source.secrets.token_hex', return_value='00112233')
    def test_estate_reads_chengdu_public_gateway(self, token_hex, requests_get, requests_post):
        time_response = MagicMock()
        time_response.json.return_value = {'data': {'timestamp': 123456}}
        time_response.raise_for_status.return_value = None
        data_response = MagicMock()
        data_response.json.return_value = {
            'data': {
                'data': [
                    {'region_type': '全市', 'dated': '2026-07-15', 'spf_countnum': 10, 'spf_area': 100, 'clf_countnum': 20, 'clf_area': 200},
                    {'region_type': '郊区新城', 'dated': '2026-07-15', 'spf_countnum': 30, 'spf_area': 300, 'clf_countnum': 40, 'clf_area': 400},
                ],
            },
        }
        data_response.raise_for_status.return_value = None
        requests_get.return_value = time_response
        requests_post.return_value = data_response
        source = EstateSource.__new__(EstateSource)
        source.logger = MagicMock()

        items = source._scrape_chengdu()

        self.assertEqual(len(items), 4)
        self.assertEqual([item for item in items if item['category'] == 'NewHome_Count'][0]['value'], 10)
        self.assertEqual([item for item in items if item['category'] == 'SecondHand_Count'][0]['value'], 20)
        self.assertEqual(items[0]['sourceDate'], '2026-07-15')

    def test_estate_parses_and_aggregates_xian_official_presales(self):
        html = '''
        <table><tr class="listtr ysztr">
          <td><a href="Lpb.aspx?yszid=A">2026328</a></td>
          <td><a href="Lpb.aspx?yszid=A">天谷府二期</a></td>
          <td>雁塔区测试地址</td><td>西安测试置业有限公司</td>
          <td>30幢,31幢</td><td>2026-07-31</td>
        </tr><tr class="listtr ysztr">
          <td><a href="Lpb.aspx?yszid=B">2026327</a></td>
          <td>航天城观山台二期</td><td>航天基地测试地址</td><td>陕西测试置业有限公司</td>
          <td>27幢、32幢、31幢</td><td>2026-07-31</td>
        </tr></table>
        '''
        events = EstateSource._parse_xian_presale_html(html, 'https://zjj.xa.gov.cn/ygsf/index.aspx')
        points = EstateSource._aggregate_xian_presales(events)

        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]['detail']['buildingCount'], 2)
        self.assertEqual(events[0]['quality'], 'official')
        self.assertTrue(events[0]['sourceUrl'].startswith('https://zjj.xa.gov.cn/ygsf/'))
        values = {item['category']: item['value'] for item in points}
        self.assertEqual(values['PresalePermit_Count'], 2)
        self.assertEqual(values['PresaleProject_Count'], 2)
        self.assertEqual(values['PresaleBuilding_Count'], 5)


if __name__ == '__main__':
    unittest.main()
