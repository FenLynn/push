import sys
import os
sys.path.insert(0, os.getcwd())

import logging
import requests
from datetime import datetime, timedelta, timezone
from core import Message, ContentType

logger = logging.getLogger('Push.Watchdog')

WATCHDOG_WORKFLOW_NAME = 'Watchdog Sentinel'
WORKFLOW_IDLE_ALERT_MINUTES = max(70, int(os.getenv('WATCHDOG_WORKFLOW_IDLE_MINUTES', '95') or '95'))


def _github_headers(token: str) -> dict:
    return {
        'Accept': 'application/vnd.github+json',
        'Authorization': f'Bearer {token}',
        'User-Agent': 'Push-Watchdog',
        'X-GitHub-Api-Version': '2022-11-28',
    }


def _parse_github_time(value: str):
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%dT%H:%M:%SZ').replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _fetch_recent_workflow_runs(limit: int = 20):
    token = os.getenv('GITHUB_TOKEN')
    repository = os.getenv('GITHUB_REPOSITORY')
    if not token or not repository:
        logger.warning('Watchdog missing GITHUB_TOKEN or GITHUB_REPOSITORY; skipping workflow idle check.')
        return []

    url = f'https://api.github.com/repos/{repository}/actions/runs'
    response = requests.get(
        url,
        headers=_github_headers(token),
        params={'per_page': limit},
        timeout=20,
    )
    response.raise_for_status()
    payload = response.json() or {}
    return payload.get('workflow_runs', []) or []


def _check_workflow_idle(now_utc: datetime):
    try:
        runs = _fetch_recent_workflow_runs(limit=30)
    except Exception as exc:
        return f'❓ GitHub Actions 最近运行记录检查失败: {exc}'

    business_runs = []
    for run in runs:
        name = str(run.get('name') or '').strip()
        if not name or name == WATCHDOG_WORKFLOW_NAME:
            continue
        started_at = _parse_github_time(run.get('run_started_at') or run.get('created_at') or '')
        if not started_at:
            continue
        business_runs.append({
            'name': name,
            'status': run.get('status') or '',
            'conclusion': run.get('conclusion') or '',
            'started_at': started_at,
            'html_url': run.get('html_url') or '',
        })

    if not business_runs:
        return '💤 GitHub Actions 最近没有业务 workflow 运行记录（排除了 Watchdog 自身）。'

    latest_run = max(business_runs, key=lambda item: item['started_at'])
    idle_minutes = (now_utc - latest_run['started_at']).total_seconds() / 60.0
    if idle_minutes <= WORKFLOW_IDLE_ALERT_MINUTES:
        logger.info(
            'Watchdog idle check ok: latest workflow=%s, idle=%.1f min',
            latest_run['name'],
            idle_minutes,
        )
        return None

    started_bjt = latest_run['started_at'].astimezone(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
    return (
        f"🚨 GitHub Actions 业务 workflow 空窗过长：最近一次是 [{latest_run['name']}]，"
        f"开始于 {started_bjt} BJT，距今约 {idle_minutes:.1f} 分钟。"
    )

def run_watchdog():
    """
    自检心跳：检查 GitHub Actions 业务 workflow 是否出现异常空窗。
    """
    now_utc = datetime.now(timezone.utc)
    now_bjt = now_utc.astimezone(timezone(timedelta(hours=8)))
    alerts = []

    idle_alert = _check_workflow_idle(now_utc)
    if idle_alert:
        alerts.append(idle_alert)

    if alerts:
        send_critical_alert("\n".join(alerts))
    else:
        logger.info("Watchdog: workflow heartbeat nominal at %s.", now_bjt.strftime('%H:%M'))

def send_critical_alert(content):
    """发送加急告警 (直接通过通道)"""
    print(f"[Watchdog Alert]\n{content}")
    msg = Message(
        title="🛡️ 哨兵拦截：系统运行异常",
        content=f"检测到以下任务未按预期执行，请检查云端状态：\n\n{content}",
        type=ContentType.TEXT,
        tags=['watchdog', 'alert']
    )
    
    try:
        from channels.pushplus import PushPlusChannel
        channel = PushPlusChannel()
        if channel.token:
            success = channel.send(msg)
            if success:
                print("[Watchdog] Critical alert sent successfully.")
            else:
                print("[Watchdog] PushPlus rejected the alert.")
        else:
            print("[Watchdog] PUSHPLUS_TOKEN not found, alert suppressed.")
    except Exception as e:
        print(f"[Watchdog] Error sending alert: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_watchdog()
