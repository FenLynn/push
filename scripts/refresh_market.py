"""Refresh stock/ETF output and notify only high-threshold daily events."""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channels.pushplus import PushPlusChannel
from core import ContentType, Message
from core.d1_client import D1Client
from core.engine import Engine
from sources.etf import ETFSource
from sources.stock import StockSource
from sources.night import NightSource


LEDGER_KEY = 'market_alert_ledger_v1'
BEIJING = timezone(timedelta(hours=8))


def _number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def collect_stock_alerts(data):
    alerts = []
    for item in data.get('indexes') or []:
        change = _number(item.get('growth_rate'))
        if change is not None and abs(change) >= 2:
            alerts.append({'key': f"index:{item.get('name')}", 'name': item.get('name'), 'change': change, 'kind': '指数'})
    for item in data.get('stocks') or []:
        change = _number(item.get('growth_rate'))
        if change is not None and abs(change) >= 5:
            alerts.append({'key': f"stock:{item.get('name')}", 'name': item.get('name'), 'change': change, 'kind': '自选'})
    return alerts


def collect_etf_alerts(data):
    alerts = []
    for item in data.get('items') or []:
        change = _number(item.get('涨跌幅'))
        if change is not None and abs(change) >= 3:
            alerts.append({'key': f"etf:{item.get('代码')}", 'name': item.get('名称'), 'change': change, 'kind': 'ETF'})
    return alerts


def collect_night_alerts(data):
    alerts = []
    for item in data.get('indexes') or []:
        change = _number(str(item.get('change') or '').replace('%', '').replace('+', ''))
        if change is not None and abs(change) >= 2.5:
            alerts.append({'key': f"night-index:{item.get('name')}", 'name': item.get('name'), 'change': change, 'kind': '海外指数'})
    for item in data.get('stocks') or []:
        change = _number(str(item.get('change') or '').replace('%', '').replace('+', ''))
        if change is not None and abs(change) >= 6:
            alerts.append({'key': f"night-stock:{item.get('name')}", 'name': item.get('name'), 'change': change, 'kind': '美股自选'})
    return alerts


class DailyLedger:
    def __init__(self, client=None):
        self.client = client or D1Client()
        if self.client.enabled:
            self.client.ensure_table('sys_kv', '''
                CREATE TABLE IF NOT EXISTS sys_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
            ''')

    def load(self):
        if not self.client.enabled:
            raise RuntimeError('D1 unavailable')
        result = self.client.query('SELECT value FROM sys_kv WHERE key = ?', [LEDGER_KEY])
        if not result.get('success'):
            raise RuntimeError(result.get('error') or 'market ledger read failed')
        data = result.get('data') or []
        rows = data[0].get('results') or [] if data and isinstance(data[0], dict) else []
        try:
            value = json.loads(rows[0].get('value') or '{}') if rows else {}
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def save(self, value):
        # A single row is retained; old daily event keys are pruned after 14 days.
        cutoff = (datetime.now(BEIJING) - timedelta(days=14)).strftime('%Y-%m-%d')
        clean = {key: day for key, day in value.items() if str(day) >= cutoff}
        result = self.client.query(
            "INSERT OR REPLACE INTO sys_kv (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            [LEDGER_KEY, json.dumps(clean, ensure_ascii=False, separators=(',', ':'))],
        )
        if not result.get('success'):
            raise RuntimeError(result.get('error') or 'market ledger write failed')


def filter_daily_alerts(alerts, ledger, day=None):
    day = day or datetime.now(BEIJING).strftime('%Y-%m-%d')
    selected = []
    for alert in alerts:
        direction = 'up' if alert['change'] > 0 else 'down'
        event_key = f"{day}:{alert['key']}:{direction}"
        if event_key in ledger:
            continue
        selected.append({**alert, 'eventKey': event_key})
    return selected


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('module', choices=['stock', 'etf', 'night'])
    args = parser.parse_args(argv)
    source_classes = {'stock': StockSource, 'etf': ETFSource, 'night': NightSource}
    source = source_classes[args.module](topic='stock', force=True)
    engine = Engine()
    engine.register_source(args.module, source)
    if not engine.run_source_only(args.module):
        raise RuntimeError(f'{args.module} refresh failed')

    collectors = {'stock': collect_stock_alerts, 'etf': collect_etf_alerts, 'night': collect_night_alerts}
    alerts = collectors[args.module](source.latest_data)
    ledger_store = DailyLedger()
    try:
        ledger = ledger_store.load()
    except Exception as exc:
        print(f'[MarketAlert] Snapshot refreshed; alert suppressed safely: {exc}')
        return 0
    selected = filter_daily_alerts(alerts, ledger)
    if not selected:
        print('[MarketAlert] No new threshold event.')
        return 0

    lines = [f"• {item['kind']} {item['name']}：{item['change']:+.2f}%" for item in selected]
    message = Message(
        title=f"市场异动 · {args.module.upper()}",
        content='本次只推送达到阈值且今日尚未提醒的事件：\n\n' + '\n'.join(lines),
        type=ContentType.TEXT,
        tags=['market', 'threshold'],
    )
    day = datetime.now(BEIJING).strftime('%Y-%m-%d')
    for item in selected:
        ledger[item['eventKey']] = day
    ledger_store.save(ledger)
    if not PushPlusChannel(topic='stock').send(message):
        raise RuntimeError('PushPlus rejected market alert; reservation retained to prevent duplicates')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
