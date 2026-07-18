from scripts.refresh_market import collect_etf_alerts, collect_night_alerts, collect_stock_alerts, filter_daily_alerts


def test_stock_alert_thresholds_are_high_signal():
    alerts = collect_stock_alerts({
        'indexes': [{'name': '上证指数', 'growth_rate': '-2.10'}, {'name': '沪深300', 'growth_rate': '-1.8'}],
        'stocks': [{'name': 'A', 'growth_rate': '5.1'}, {'name': 'B', 'growth_rate': '4.9'}],
    })
    assert [item['name'] for item in alerts] == ['上证指数', 'A']


def test_etf_alert_is_only_once_per_direction_per_day():
    alerts = collect_etf_alerts({'items': [{'代码': '510300', '名称': '沪深300ETF', '涨跌幅': -3.2}]})
    first = filter_daily_alerts(alerts, {}, day='2026-07-18')
    assert len(first) == 1
    ledger = {first[0]['eventKey']: '2026-07-18'}
    assert filter_daily_alerts(alerts, ledger, day='2026-07-18') == []


def test_night_alerts_use_a_higher_threshold():
    alerts = collect_night_alerts({
        'indexes': [{'name': 'NASDAQ', 'change': '-2.6'}, {'name': 'S&P 500', 'change': '-2.4'}],
        'stocks': [{'name': 'NVDA', 'change': '+6.2'}, {'name': 'AAPL', 'change': '+5.9'}],
    })
    assert [item['name'] for item in alerts] == ['NASDAQ', 'NVDA']
