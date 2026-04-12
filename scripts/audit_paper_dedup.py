#!/usr/bin/env python3
"""Paper 去重/竞态审计脚本。"""

import json
import os
import sys
from datetime import UTC, datetime

from dotenv import load_dotenv


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from core.d1_client import D1Client


OUTPUT_DIR = os.path.join(ROOT_DIR, 'output', 'paper', 'audit')
PUSH_SEEN_TABLE = 'paper_push_seen'
WINDOW_HOURS = int(os.getenv('PAPER_PAST_HOURS', '25') or '25')
RETENTION_DAYS = int(os.getenv('PAPER_ARTICLE_RETENTION_DAYS', os.getenv('PAPER_SNAPSHOT_RETENTION_DAYS', '7')) or '7')


def extract_rows(result):
    if not result.get('success'):
        raise RuntimeError(result.get('error') or 'D1 query failed')
    data = result.get('data') or []
    if not data:
        return []
    first = data[0] if isinstance(data, list) else {}
    rows = first.get('results') if isinstance(first, dict) else []
    return rows if isinstance(rows, list) else []


def scalar_row(client, sql, params=None):
    rows = extract_rows(client.query(sql, params or []))
    return rows[0] if rows else {}


def safe_scalar_row(client, sql, params=None, default=None):
    try:
        return scalar_row(client, sql, params)
    except RuntimeError as exc:
        if 'no such table' in str(exc).lower():
            return default or {}
        raise


def safe_extract_rows(client, sql, params=None, default=None):
    try:
        return extract_rows(client.query(sql, params or []))
    except RuntimeError as exc:
        if 'no such table' in str(exc).lower():
            return default or []
        raise


def table_exists(client, table_name):
    row = scalar_row(
        client,
        "SELECT COUNT(*) AS cnt FROM sqlite_master WHERE type = 'table' AND name = ?",
        [table_name],
    )
    try:
        return int(row.get('cnt', 0) or 0) > 0
    except (TypeError, ValueError):
        return False


def main():
    load_dotenv(os.path.join(ROOT_DIR, '.env'))

    client = D1Client()
    if not client.enabled:
        raise SystemExit('D1 未启用，无法执行 paper 审计。')

    os.makedirs(OUTPUT_DIR, exist_ok=True)
    push_seen_exists = table_exists(client, PUSH_SEEN_TABLE)

    summary = {
        'generatedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'windowHours': WINDOW_HOURS,
        'retentionDays': RETENTION_DAYS,
        'articlesRecent': scalar_row(
            client,
            f"SELECT COUNT(*) as cnt, MIN(created_at) as oldest, MAX(created_at) as newest FROM articles WHERE created_at > datetime('now', '-{WINDOW_HOURS} hours')"
        ),
        'articlesRecentOldPublished': scalar_row(
            client,
            f"SELECT COUNT(*) as cnt FROM articles WHERE created_at > datetime('now', '-{WINDOW_HOURS} hours') AND published_at <= datetime('now', '-{RETENTION_DAYS} days')"
        ),
        'articlesRecentSourceBreakdown': safe_extract_rows(
            client,
            f"""
            SELECT source_name,
                   COUNT(*) as total,
                   SUM(CASE WHEN published_at <= datetime('now', '-{RETENTION_DAYS} days') THEN 1 ELSE 0 END) as old_published
            FROM articles
            WHERE created_at > datetime('now', '-{WINDOW_HOURS} hours')
            GROUP BY source_name
            ORDER BY total DESC, source_name ASC
            LIMIT 80
            """
        ),
        'paperPushSeen': {
            'tableExists': push_seen_exists,
            'summary': (
                scalar_row(
                    client,
                    f"SELECT COUNT(*) as cnt, MIN(last_pushed_at) as earliest, MAX(last_pushed_at) as latest FROM {PUSH_SEEN_TABLE}"
                )
                if push_seen_exists
                else {'cnt': 0, 'earliest': None, 'latest': None}
            ),
            'recent': (
                extract_rows(
                    client.query(
                        f"SELECT dedupe_kind, source_name, title, doi, published_at, first_seen_created_at, last_pushed_at, push_count FROM {PUSH_SEEN_TABLE} ORDER BY last_pushed_at DESC LIMIT 80"
                    )
                )
                if push_seen_exists
                else []
            ),
        },
    }

    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    latest_path = os.path.join(OUTPUT_DIR, 'latest_dedup_audit.json')
    archive_path = os.path.join(OUTPUT_DIR, f'dedup_audit_{stamp}.json')
    payload = json.dumps(summary, ensure_ascii=False, indent=2)

    with open(latest_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(payload)
    with open(archive_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(payload)

    print(f'Dedup audit saved: {archive_path}')
    print(json.dumps({
        'articlesRecent': summary['articlesRecent'],
        'articlesRecentOldPublished': summary['articlesRecentOldPublished'],
        'paperPushSeenSummary': summary['paperPushSeen']['summary'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()