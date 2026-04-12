#!/usr/bin/env python3
"""把 paper 旧行中已存在于 content/link 的元数据回填到新列。"""

import json
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

from core.d1_client import D1Client
from scripts.fetch_to_d1 import backfill_recent_embedded_metadata, ensure_articles_schema, write_crossref_audit


def main():
    load_dotenv(os.path.join(ROOT_DIR, '.env'))
    d1 = D1Client()
    if not d1.enabled:
        raise SystemExit('D1 未启用，无法执行 embedded metadata 回填。')

    ensure_articles_schema(d1)
    lookback_hours = max(1, int(os.getenv('PAPER_EMBEDDED_BACKFILL_LOOKBACK_HOURS', '30') or '30'))
    limit = max(1, int(os.getenv('PAPER_EMBEDDED_BACKFILL_LIMIT', '500') or '500'))

    summary = backfill_recent_embedded_metadata(d1, lookback_hours=lookback_hours, limit=limit)
    summary['mode'] = 'embedded-only'
    audit_path = write_crossref_audit(summary, label='embedded_backfill')

    print(f'Embedded metadata audit saved: {audit_path}')
    print(json.dumps({
        'lookbackHours': summary['lookbackHours'],
        'limit': summary['limit'],
        'scanned': summary['scanned'],
        'updated': summary['updated'],
        'doiFilled': summary['doiFilled'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()