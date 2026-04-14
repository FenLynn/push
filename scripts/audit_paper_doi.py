#!/usr/bin/env python3
"""审计最近 paper 文章 DOI 缺口。"""

import json
import os
import sys
from datetime import datetime, timezone

UTC = timezone.utc


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

from core.d1_client import D1Client
from scripts.fetch_to_d1 import ensure_audit_dir, query_rows


def main():
    load_dotenv(os.path.join(ROOT_DIR, '.env'))
    d1 = D1Client()
    if not d1.enabled:
        raise SystemExit('D1 未启用，无法执行 DOI 审计。')

    lookback_hours = max(1, int(os.getenv('PAPER_DOI_AUDIT_LOOKBACK_HOURS', '168') or '168'))

    summary_row = query_rows(
        d1,
        """
        SELECT COUNT(*) AS total,
               SUM(CASE WHEN COALESCE(doi, '') = '' THEN 1 ELSE 0 END) AS missing_doi,
               SUM(CASE WHEN COALESCE(doi, '') != '' THEN 1 ELSE 0 END) AS with_doi
        FROM articles
        WHERE created_at > datetime('now', ?)
          AND source_type = 'journal'
        """,
        [f'-{lookback_hours} hours']
    )
    sample_rows = query_rows(
        d1,
        """
        SELECT source_name, title, created_at, published_at, link
        FROM articles
        WHERE created_at > datetime('now', ?)
          AND source_type = 'journal'
          AND COALESCE(doi, '') = ''
        ORDER BY created_at DESC
        LIMIT 20
        """,
        [f'-{lookback_hours} hours']
    )

    payload = {
        'generatedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'lookbackHours': lookback_hours,
        'summary': summary_row[0] if summary_row else {'total': 0, 'missing_doi': 0, 'with_doi': 0},
        'samples': sample_rows,
    }

    out_dir = ensure_audit_dir()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    latest_path = os.path.join(out_dir, 'latest_doi_audit.json')
    archive_path = os.path.join(out_dir, f'doi_audit_{stamp}.json')
    body = json.dumps(payload, ensure_ascii=False, indent=2)
    with open(latest_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(body)
    with open(archive_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(body)

    print(f'DOI audit saved: {archive_path}')
    print(json.dumps(payload['summary'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()