import unittest
from unittest.mock import MagicMock, patch

from sources.stock.source import StockSource


class StockSnapshotTests(unittest.TestCase):
    @patch('sources.stock.source.export_dashboard_snapshot')
    def test_exports_mean_and_median_to_fixed_stock_snapshot(self, export_snapshot):
        export_snapshot.return_value = {'success': True}
        source = StockSource.__new__(StockSource)
        source.df_all = [None] * 1200
        source.logger = MagicMock()

        source._export_market_breadth_snapshot({
            'summary': {'mean': '1.234', 'median': '-0.456', 'sample_size': 1187},
        })

        export_snapshot.assert_called_once()
        module_name, payload = export_snapshot.call_args.args
        self.assertEqual(module_name, 'stock')
        self.assertEqual(payload['breadth']['avgChange'], 1.23)
        self.assertEqual(payload['breadth']['medianChange'], -0.46)
        self.assertEqual(payload['breadth']['sampleSize'], 1187)

    @patch('sources.stock.source.export_dashboard_snapshot')
    def test_keeps_previous_snapshot_when_market_statistics_are_missing(self, export_snapshot):
        source = StockSource.__new__(StockSource)
        source.df_all = [None] * 1200
        source.logger = MagicMock()

        source._export_market_breadth_snapshot({
            'summary': {'mean': '-', 'median': '-'},
        })

        export_snapshot.assert_not_called()

    @patch('sources.stock.source.export_dashboard_snapshot')
    def test_rejects_snapshot_with_too_few_valid_rows(self, export_snapshot):
        source = StockSource.__new__(StockSource)
        source.df_all = [None] * 1200
        source.logger = MagicMock()

        source._export_market_breadth_snapshot({
            'summary': {'mean': '0.12', 'median': '0.08', 'sample_size': 999},
        })

        export_snapshot.assert_not_called()


if __name__ == '__main__':
    unittest.main()
