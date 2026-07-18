"""Low-noise GitHub Actions watchdog with a persistent 48-hour alert threshold."""

from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone

import requests

sys.path.insert(0, os.getcwd())

from core import ContentType, Message
from core.d1_client import D1Client


logger = logging.getLogger('Push.Watchdog')
WATCHDOG_WORKFLOW_NAME = 'Watchdog Sentinel'
STATE_KEY = 'watchdog_persistent_state_v2'
PERSIST_HOURS = max(48, int(os.getenv('WATCHDOG_PERSIST_HOURS', '48') or '48'))
IDLE_HOURS = max(3, int(os.getenv('WATCHDOG_BUSINESS_IDLE_HOURS', '4') or '4'))
FAILED_CONCLUSIONS = {'failure', 'cancelled', 'timed_out', 'action_required', 'stale'}


def _github_headers(token):
    return {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Push-Watchdog',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def _parse_time(value):
    try:
        return datetime.fromisoformat(str(value or '').replace('Z', '+00:00'))
    except ValueError:
        return None


def fetch_recent_workflow_runs(limit=100):
    token = os.getenv('GITHUB_TOKEN')
    repository = os.getenv('GITHUB_REPOSITORY')
    if not token or not repository:
        raise RuntimeError('missing GITHUB_TOKEN or GITHUB_REPOSITORY')
    response = requests.get(
        f'https://api.github.com/repos/{repository}/actions/runs',
        headers=_github_headers(token),
        params={'per_page': min(100, max(1, limit))},
        timeout=20,
    )
    response.raise_for_status()
    return (response.json() or {}).get('workflow_runs') or []


def detect_issues(runs, now=None):
    now = now or datetime.now(timezone.utc)
    latest_by_workflow = {}
    business_runs = []
    for run in runs:
        name = str(run.get('name') or '').strip()
        if not name or name == WATCHDOG_WORKFLOW_NAME:
            continue
        started_at = _parse_time(run.get('run_started_at') or run.get('created_at'))
        if not started_at:
            continue
        item = {
            'name': name,
            'startedAt': started_at,
            'status': str(run.get('status') or ''),
            'conclusion': str(run.get('conclusion') or ''),
            'url': str(run.get('html_url') or ''),
        }
        business_runs.append(item)
        if name not in latest_by_workflow or started_at > latest_by_workflow[name]['startedAt']:
            latest_by_workflow[name] = item

    issues = {}
    for name, item in latest_by_workflow.items():
        if item['status'] == 'completed' and item['conclusion'] in FAILED_CONCLUSIONS:
            issues[f'workflow:{name}'] = (
                f"{name} 最近一次运行仍为 {item['conclusion']}，"
                f"开始于 {item['startedAt'].astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M')} BJT。"
            )

    if not business_runs:
        issues['workflow:idle'] = 'GitHub Actions 没有可读取的业务运行记录。'
    else:
        latest = max(business_runs, key=lambda item: item['startedAt'])
        idle_hours = (now - latest['startedAt']).total_seconds() / 3600
        if idle_hours >= IDLE_HOURS:
            issues['workflow:idle'] = (
                f"业务 workflow 已连续约 {idle_hours:.1f} 小时没有运行；"
                f"最近一次是 {latest['name']}。"
            )
    return issues


def evaluate_alert_state(state, issues, now=None):
    now = now or datetime.now(timezone.utc)
    now_text = now.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z')
    old = state.get('issues') if isinstance(state, dict) and isinstance(state.get('issues'), dict) else {}
    current = {}
    due = []
    for issue_id, message in issues.items():
        previous = old.get(issue_id) if isinstance(old.get(issue_id), dict) else {}
        first_seen = _parse_time(previous.get('firstSeen')) or now
        record = {
            'firstSeen': first_seen.astimezone(timezone.utc).isoformat().replace('+00:00', 'Z'),
            'lastSeen': now_text,
            'message': str(message),
            'notifiedAt': str(previous.get('notifiedAt') or ''),
        }
        if (now - first_seen) >= timedelta(hours=PERSIST_HOURS) and not record['notifiedAt']:
            due.append((issue_id, record['message']))
        current[issue_id] = record
    return {'version': 2, 'updatedAt': now_text, 'issues': current}, due


def _result_rows(result):
    data = result.get('data') or [] if result.get('success') else []
    return data[0].get('results') or [] if data and isinstance(data[0], dict) else []


class WatchdogStateStore:
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
            raise RuntimeError('D1 is unavailable')
        result = self.client.query('SELECT value FROM sys_kv WHERE key = ?', [STATE_KEY])
        if not result.get('success'):
            raise RuntimeError(result.get('error') or 'watchdog state read failed')
        rows = _result_rows(result)
        if not rows:
            return {}
        try:
            value = json.loads(rows[0].get('value') or '{}')
            return value if isinstance(value, dict) else {}
        except (TypeError, ValueError):
            return {}

    def save(self, state):
        result = self.client.query(
            "INSERT OR REPLACE INTO sys_kv (key, value, updated_at) VALUES (?, ?, datetime('now'))",
            [STATE_KEY, json.dumps(state, ensure_ascii=False, separators=(',', ':'))],
        )
        if not result.get('success'):
            raise RuntimeError(result.get('error') or 'watchdog state write failed')


def send_critical_alert(due):
    from channels.pushplus import PushPlusChannel

    content = '\n'.join(f'• {message}' for _, message in due)
    message = Message(
        title='🛡️ 持续 48 小时的系统故障',
        content=f'以下故障已持续至少 {PERSIST_HOURS} 小时，短期波动已自动忽略：\n\n{content}',
        type=ContentType.TEXT,
        tags=['watchdog', 'persistent-alert'],
    )
    if not PushPlusChannel(topic='me').send(message):
        raise RuntimeError('PushPlus rejected watchdog alert')


def run_watchdog():
    now = datetime.now(timezone.utc)
    try:
        issues = detect_issues(fetch_recent_workflow_runs(), now=now)
    except Exception as exc:
        issues = {'watchdog:github-api': f'Watchdog 无法检查 GitHub Actions：{exc}'}

    store = WatchdogStateStore()
    try:
        state, due = evaluate_alert_state(store.load(), issues, now=now)
        # Persist first so a send retry cannot erase the original firstSeen timestamp.
        store.save(state)
    except Exception as exc:
        logger.error('Watchdog state unavailable; suppressing alert to avoid noisy stateless retries: %s', exc)
        return

    if due:
        send_critical_alert(due)
        notified_at = now.isoformat().replace('+00:00', 'Z')
        for issue_id, _ in due:
            if issue_id in state['issues']:
                state['issues'][issue_id]['notifiedAt'] = notified_at
        store.save(state)
        logger.warning('Watchdog notified %s persistent issue(s).', len(due))
    else:
        logger.info('Watchdog checked %s active issue(s); none has crossed %sh.', len(issues), PERSIST_HOURS)


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    run_watchdog()
