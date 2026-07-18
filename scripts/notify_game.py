"""Send one important LoL match alert at most once, backed by a bounded D1 ledger."""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from channels.pushplus import PushPlusChannel
from core import ContentType, Message
from core.d1_client import D1Client
from core.utils.lol_esports import BEIJING_TZ, fetch_watched_matches


LEDGER_KEY = 'game_notification_ledger_v1'
LEDGER_RETENTION_DAYS = 90
NOTIFY_AHEAD_MINUTES = 90


def _rows(result):
    if not result.get('success'):
        return []
    data = result.get('data') or []
    return data[0].get('results') or [] if data and isinstance(data[0], dict) else []


class NotificationLedger:
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

    @property
    def enabled(self):
        return bool(self.client.enabled)

    def load(self, now=None):
        now = now or datetime.now(timezone.utc)
        result = self.client.query('SELECT value FROM sys_kv WHERE key = ?', [LEDGER_KEY])
        if not result.get('success'):
            raise RuntimeError(result.get('error') or 'D1 ledger read failed')
        rows = _rows(result)
        try:
            entries = json.loads(rows[0].get('value') or '{}') if rows else {}
        except (TypeError, ValueError):
            entries = {}
        cutoff = now - timedelta(days=LEDGER_RETENTION_DAYS)
        cleaned = {}
        for match_id, sent_at in (entries.items() if isinstance(entries, dict) else []):
            try:
                parsed = datetime.fromisoformat(str(sent_at).replace('Z', '+00:00'))
            except ValueError:
                continue
            if parsed >= cutoff:
                cleaned[str(match_id)] = parsed.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
        return dict(list(cleaned.items())[-200:])

    def save(self, entries):
        value = json.dumps(dict(list(entries.items())[-200:]), ensure_ascii=False, separators=(',', ':'))
        result = self.client.query(
            "INSERT OR REPLACE INTO sys_kv (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            [LEDGER_KEY, value],
        )
        if not result.get('success'):
            raise RuntimeError(result.get('error') or 'D1 ledger write failed')


def select_notification_candidates(matches, ledger, now=None):
    now = now or datetime.now(timezone.utc)
    deadline = now + timedelta(minutes=NOTIFY_AHEAD_MINUTES)
    candidates = []
    for match in matches:
        match_id = str(match.get('providerId') or match.get('id') or '').strip()
        if not match_id or match_id in ledger or match.get('status') == 'completed':
            continue
        try:
            starts_at = datetime.fromisoformat(str(match.get('startTime') or '').replace('Z', '+00:00'))
        except ValueError:
            continue
        if match.get('live') or now <= starts_at <= deadline:
            candidates.append(match)
    return candidates


def _message_for(match):
    start = datetime.fromisoformat(match['startTime'].replace('Z', '+00:00')).astimezone(BEIJING_TZ)
    score = f"当前比分 {match.get('scoreText')}，第 {match.get('currentGame')} 局" if match.get('live') else '即将开始'
    bo = f"BO{match.get('bestOf')}" if match.get('bestOf') else ''
    title = f"🔴 {match.get('teamACode') or match.get('teamA')} vs {match.get('teamBCode') or match.get('teamB')}"
    content = (
        f"{match.get('league')} {match.get('stage')} {bo}\n"
        f"北京时间：{start.strftime('%m月%d日 %H:%M')}\n"
        f"{match.get('teamA')} {match.get('scoreA', 0)} : {match.get('scoreB', 0)} {match.get('teamB')}\n"
        f"{score}\n{match.get('streamUrl') or 'https://lolesports.com/en-US'}"
    )
    return Message(title=title, content=content, type=ContentType.TEXT, tags=['game', 'important'])


def main():
    ledger_store = NotificationLedger()
    if not ledger_store.enabled:
        print('[GameNotify] D1 is unavailable; suppressing notification to guarantee no duplicates.')
        return 0
    try:
        ledger = ledger_store.load()
        candidates = select_notification_candidates(fetch_watched_matches(days_after=3), ledger)
    except Exception as exc:
        print(f'[GameNotify] Safe skip before sending: {exc}')
        return 0
    if not candidates:
        print('[GameNotify] No new watched match within the notification window.')
        return 0

    channel = PushPlusChannel(topic='baobao')
    for match in candidates:
        match_id = str(match.get('providerId') or match.get('id'))
        # Reserve before the external send. This intentionally provides at-most-once
        # delivery if the process is interrupted after PushPlus accepts the request.
        ledger[match_id] = datetime.now(timezone.utc).isoformat().replace('+00:00', 'Z')
        ledger_store.save(ledger)
        if not channel.send(_message_for(match)):
            print(f'[GameNotify] PushPlus rejected {match_id}; reservation retained to prevent duplicates.')
            continue
        print(f'[GameNotify] Sent and recorded {match_id}.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
