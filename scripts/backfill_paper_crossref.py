#!/usr/bin/env python3
"""回填最近 paper 文章的 Crossref/DOI 元数据。"""

import json
import os
import sys


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

from dotenv import load_dotenv

from core.d1_client import D1Client
from scripts.fetch_to_d1 import (
    backfill_recent_embedded_metadata,
    ensure_articles_schema,
    enrich_recent_articles_with_crossref,
    write_crossref_audit,
)


def main():
    load_dotenv(os.path.join(ROOT_DIR, '.env'))

    d1 = D1Client()
    if not d1.enabled:
        raise SystemExit('D1 未启用，无法执行 Crossref 回填。')

    ensure_articles_schema(d1)

    lookback_hours = max(1, int(os.getenv('PAPER_CROSSREF_BACKFILL_LOOKBACK_HOURS', os.getenv('PAPER_CROSSREF_LOOKBACK_HOURS', '168')) or '168'))
    limit = max(1, int(os.getenv('PAPER_CROSSREF_BACKFILL_LIMIT', '160') or '160'))

    print(f'Crossref backfill started: lookback={lookback_hours}h, limit={limit}')

    embedded_summary = backfill_recent_embedded_metadata(d1, lookback_hours=lookback_hours, limit=max(limit * 4, 120))
    print(json.dumps({
        'embeddedScanned': embedded_summary['scanned'],
        'embeddedUpdated': embedded_summary['updated'],
        'embeddedDoiFilled': embedded_summary['doiFilled'],
    }, ensure_ascii=False, indent=2))

    summary = enrich_recent_articles_with_crossref(d1, lookback_hours=lookback_hours, limit=limit)
    summary['mode'] = 'manual-backfill'
    summary['embeddedMetadata'] = embedded_summary
    audit_path = write_crossref_audit(summary, label='crossref_backfill')

    print(f'Crossref backfill audit saved: {audit_path}')
    print(json.dumps({
        'lookbackHours': summary['lookbackHours'],
        'limit': summary['limit'],
        'candidates': summary['candidates'],
        'matched': summary['matched'],
        'updated': summary['updated'],
        'doiFilled': summary['doiFilled'],
    }, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()