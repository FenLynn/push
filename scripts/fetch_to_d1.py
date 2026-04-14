import concurrent.futures
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

UTC = timezone.utc

# Add project root to sys.path to import core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import requests
    import feedparser
    from dotenv import load_dotenv
    from core.config import config
    from core.d1_client import D1Client
    from core.kv_client import CloudflareKVClient
    
    # Load .env explicitly for local run
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
except ImportError:
    print("Missing dependencies. Please run: pip install feedparser requests python-dotenv")
    sys.exit(1)

# Configuration from env or default
D1_TABLE = "articles"
ARTICLE_STATE_TABLE = 'paper_article_state'
SNAPSHOT_OUTPUT_KEY = os.getenv('OPTICS_SNAPSHOT_KV_KEY', 'dashboard:snapshot:optics:latest')
SNAPSHOT_MAX_ITEMS = max(200, int(os.getenv('PAPER_SNAPSHOT_MAX_ITEMS', '1200')))
SNAPSHOT_RETENTION_DAYS = max(1, int(os.getenv('PAPER_SNAPSHOT_RETENTION_DAYS', '7')))
ARTICLE_RETENTION_DAYS = max(1, int(os.getenv('PAPER_ARTICLE_RETENTION_DAYS', str(SNAPSHOT_RETENTION_DAYS))))
INGEST_STALE_HOURS = max(1, int(os.getenv('PAPER_INGEST_STALE_HOURS', '3') or '3'))
LEGACY_FINALIZE_DELAY_MINUTES = max(5, int(os.getenv('PAPER_LEGACY_FINALIZE_DELAY_MINUTES', '30') or '30'))
CROSSREF_BASE = 'https://api.crossref.org/works/'
CROSSREF_SEARCH_BASE = 'https://api.crossref.org/works'
CROSSREF_LOOKBACK_HOURS = max(1, int(os.getenv('PAPER_CROSSREF_LOOKBACK_HOURS', '72') or '72'))
CROSSREF_MAX_ENRICH_PER_RUN = max(0, int(os.getenv('PAPER_CROSSREF_MAX_ENRICH_PER_RUN', '60') or '60'))
CROSSREF_SEARCH_ROWS = max(3, int(os.getenv('PAPER_CROSSREF_SEARCH_ROWS', '8') or '8'))
CROSSREF_TITLE_ROWS = max(3, int(os.getenv('PAPER_CROSSREF_TITLE_ROWS', '6') or '6'))
CROSSREF_RETRY_COUNT = max(0, int(os.getenv('PAPER_CROSSREF_RETRY_COUNT', '2') or '2'))
CROSSREF_MAILTO = str(os.getenv('CROSSREF_MAILTO', '') or '').strip()
ARTICLE_EXTRA_COLUMNS = {
    'doi': 'TEXT',
    'authors': 'TEXT',
    'volume': 'TEXT',
    'issue': 'TEXT',
    'pages': 'TEXT',
    'metadata_source': 'TEXT',
    'crossref_updated_at': 'TEXT',
    'ingest_batch_id': 'TEXT',
    'ingest_finalized_at': 'TEXT',
    'first_seen_at': 'TEXT',
    'last_seen_at': 'TEXT',
}

DOI_PATTERN = re.compile(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')
ARTICLE_META_CACHE = {}
DEDUPE_QUERY_PARAM_BLOCKLIST = {
    'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
    'gclid', 'fbclid', 'mc_cid', 'mc_eid', 'ref', 'source'
}


def normalize_doi(value):
    match = DOI_PATTERN.search(str(value or ''))
    if not match:
        return ''
    return match.group(1).rstrip(').,;]').upper()


def normalize_title_for_identity(value=''):
    text = TAG_RE.sub(' ', str(value or ''))
    text = text.replace('—', '-').replace('–', '-')
    return re.sub(r'\s+', ' ', text).strip().lower()


def normalize_link_for_identity(link=''):
    raw_link = str(link or '').strip()
    if not raw_link:
        return ''

    try:
        parts = urlsplit(raw_link)
        filtered_query = []
        for key, value in parse_qsl(parts.query, keep_blank_values=True):
            if key.lower() in DEDUPE_QUERY_PARAM_BLOCKLIST:
                continue
            filtered_query.append((key, value))
        return urlunsplit((
            parts.scheme.lower(),
            parts.netloc.lower(),
            parts.path.rstrip('/'),
            urlencode(filtered_query, doseq=True),
            '',
        )).strip()
    except Exception:
        return raw_link


def build_article_identity(title='', link='', doi='', source_name=''):
    normalized_doi = normalize_doi(doi)
    normalized_title = normalize_title_for_identity(title)
    normalized_source = normalize_title_for_identity(source_name)
    normalized_link = normalize_link_for_identity(link)

    if normalized_source and normalized_title:
        raw_key = f'title|{normalized_source}|{normalized_title}'
        dedupe_kind = 'title'
    elif normalized_doi:
        raw_key = f'doi|{normalized_doi}'
        dedupe_kind = 'doi'
    elif normalized_link:
        raw_key = f'link|{normalized_link}'
        dedupe_kind = 'link'
    else:
        raw_key = f'fallback|{normalized_source}|{normalized_title}|{link}'
        dedupe_kind = 'fallback'

    return {
        'dedupe_key': f'{dedupe_kind}:{hashlib.sha256(raw_key.encode("utf-8")).hexdigest()}',
        'dedupe_kind': dedupe_kind,
        'source_name': str(source_name or '').strip(),
        'title': str(title or '').strip(),
        'link': str(link or '').strip(),
        'doi': normalized_doi,
    }


def merge_metadata_sources(*values):
    merged = []
    seen = set()
    for value in values:
        for item in str(value or '').split('+'):
            token = item.strip().lower()
            if not token or token in seen:
                continue
            seen.add(token)
            merged.append(token)
    return '+'.join(merged)


def crossref_headers():
    user_agent = 'PushPaperCrossref/1.0'
    if CROSSREF_MAILTO:
        user_agent = f'{user_agent} (mailto:{CROSSREF_MAILTO})'
    return {
        'User-Agent': user_agent,
        'Accept': 'application/json',
    }


def fetch_crossref_json(url, params=None):
    last_payload = None
    for attempt in range(CROSSREF_RETRY_COUNT + 1):
        try:
            response = requests.get(
                url,
                params=params,
                headers=crossref_headers(),
                timeout=20,
                proxies={"http": None, "https": None},
            )
        except Exception:
            if attempt >= CROSSREF_RETRY_COUNT:
                return None
            continue

        if response.status_code == 200:
            try:
                return response.json()
            except ValueError:
                return None

        if response.status_code in {404}:
            return None

        last_payload = response.text[:400]
        if response.status_code not in {408, 425, 429, 500, 502, 503, 504}:
            break

    return None if last_payload is None else None


def ensure_audit_dir():
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output', 'paper', 'audit')
    os.makedirs(out_dir, exist_ok=True)
    return out_dir


def write_ingest_audit(summary):
    out_dir = ensure_audit_dir()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    latest_path = os.path.join(out_dir, 'latest_ingest_audit.json')
    archive_path = os.path.join(out_dir, f'ingest_{stamp}.json')
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    with open(latest_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(payload)
    with open(archive_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(payload)
    return archive_path


def write_crossref_audit(summary, label='crossref'):
    out_dir = ensure_audit_dir()
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    latest_path = os.path.join(out_dir, f'latest_{label}_audit.json')
    archive_path = os.path.join(out_dir, f'{label}_{stamp}.json')
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    with open(latest_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(payload)
    with open(archive_path, 'w', encoding='utf-8') as file_obj:
        file_obj.write(payload)
    return archive_path


def is_entry_within_retention(dt, now=None):
    reference = now or datetime.now()
    return dt >= reference - timedelta(days=ARTICLE_RETENTION_DAYS)


def query_rows(d1_client, sql, params=None):
    result = d1_client.query(sql, params or [])
    if not result.get('success'):
        raise RuntimeError(result.get('error') or 'D1 query failed')

    data = result.get('data') or []
    if not data:
        return []

    first = data[0] if isinstance(data, list) else {}
    rows = first.get('results') if isinstance(first, dict) else []
    return rows if isinstance(rows, list) else []


def ensure_articles_schema(d1_client):
    existing_columns = {str(row.get('name') or '').strip().lower() for row in query_rows(d1_client, f'PRAGMA table_info({D1_TABLE})')}
    for column_name, column_type in ARTICLE_EXTRA_COLUMNS.items():
        if column_name.lower() in existing_columns:
            continue
        print(f'Adding articles column: {column_name}')
        d1_client.query(f'ALTER TABLE {D1_TABLE} ADD COLUMN {column_name} {column_type}')

    d1_client.query('CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi)')
    d1_client.query('CREATE INDEX IF NOT EXISTS idx_articles_crossref_updated ON articles(crossref_updated_at)')
    d1_client.query('CREATE INDEX IF NOT EXISTS idx_articles_ingest_finalized ON articles(ingest_finalized_at)')
    d1_client.query('CREATE INDEX IF NOT EXISTS idx_articles_ingest_batch ON articles(ingest_batch_id)')
    d1_client.query('CREATE INDEX IF NOT EXISTS idx_articles_first_seen ON articles(first_seen_at)')
    d1_client.query('CREATE INDEX IF NOT EXISTS idx_articles_last_seen ON articles(last_seen_at)')


def ensure_article_state_table(d1_client):
    schema = f"""
    CREATE TABLE IF NOT EXISTS {ARTICLE_STATE_TABLE} (
        dedupe_key TEXT PRIMARY KEY,
        dedupe_kind TEXT,
        source_name TEXT,
        title TEXT,
        link TEXT,
        doi TEXT,
        first_seen_at TEXT,
        last_seen_at TEXT,
        first_published_at TEXT,
        last_published_at TEXT,
        seen_count INTEGER DEFAULT 1,
        updated_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_article_state_first_seen ON {ARTICLE_STATE_TABLE}(first_seen_at);
    CREATE INDEX IF NOT EXISTS idx_article_state_last_seen ON {ARTICLE_STATE_TABLE}(last_seen_at);
    CREATE INDEX IF NOT EXISTS idx_article_state_source ON {ARTICLE_STATE_TABLE}(source_name, last_seen_at);
    """
    d1_client.ensure_table(ARTICLE_STATE_TABLE, schema)


def backfill_article_seen_columns(d1_client):
    count_rows = query_rows(
        d1_client,
        "SELECT COUNT(*) AS cnt FROM articles WHERE COALESCE(first_seen_at, '') = '' OR COALESCE(last_seen_at, '') = ''",
    )
    pending = int((count_rows[0] if count_rows else {}).get('cnt', 0) or 0)
    if pending <= 0:
        return {'updated': 0}

    d1_client.query(
        """
        UPDATE articles
        SET first_seen_at = COALESCE(NULLIF(first_seen_at, ''), created_at),
            last_seen_at = COALESCE(NULLIF(last_seen_at, ''), created_at)
        WHERE COALESCE(first_seen_at, '') = ''
           OR COALESCE(last_seen_at, '') = ''
        """
    )
    return {'updated': pending}


def upsert_article_state(d1_client, identity, first_seen_at='', last_seen_at='', published_at=''):
    table_name = ARTICLE_STATE_TABLE
    first_seen_text = str(first_seen_at or '').strip()
    last_seen_text = str(last_seen_at or first_seen_at or '').strip()
    published_text = str(published_at or '').strip()
    updated_at = last_seen_text or datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    sql = f"""
    INSERT INTO {table_name}
    (dedupe_key, dedupe_kind, source_name, title, link, doi, first_seen_at, last_seen_at, first_published_at, last_published_at, seen_count, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
    ON CONFLICT(dedupe_key) DO UPDATE SET
        dedupe_kind = excluded.dedupe_kind,
        source_name = COALESCE(NULLIF(excluded.source_name, ''), {table_name}.source_name),
        title = COALESCE(NULLIF(excluded.title, ''), {table_name}.title),
        link = COALESCE(NULLIF(excluded.link, ''), {table_name}.link),
        doi = COALESCE(NULLIF({table_name}.doi, ''), NULLIF(excluded.doi, ''), {table_name}.doi),
        first_seen_at = CASE
            WHEN COALESCE(NULLIF({table_name}.first_seen_at, ''), '') = '' THEN excluded.first_seen_at
            WHEN COALESCE(NULLIF(excluded.first_seen_at, ''), '') = '' THEN {table_name}.first_seen_at
            WHEN datetime(excluded.first_seen_at) < datetime({table_name}.first_seen_at) THEN excluded.first_seen_at
            ELSE {table_name}.first_seen_at
        END,
        last_seen_at = COALESCE(NULLIF(excluded.last_seen_at, ''), {table_name}.last_seen_at),
        first_published_at = CASE
            WHEN COALESCE(NULLIF({table_name}.first_published_at, ''), '') = '' THEN excluded.first_published_at
            WHEN COALESCE(NULLIF(excluded.first_published_at, ''), '') = '' THEN {table_name}.first_published_at
            WHEN datetime(excluded.first_published_at) < datetime({table_name}.first_published_at) THEN excluded.first_published_at
            ELSE {table_name}.first_published_at
        END,
        last_published_at = COALESCE(NULLIF(excluded.last_published_at, ''), {table_name}.last_published_at),
        seen_count = {table_name}.seen_count + 1,
        updated_at = excluded.updated_at
    """
    params = [
        identity['dedupe_key'], identity['dedupe_kind'], identity['source_name'], identity['title'], identity['link'],
        identity['doi'], first_seen_text, last_seen_text, published_text, published_text, updated_at,
    ]
    return d1_client.query(sql, params)


def sync_article_state_from_articles(d1_client, limit=2400):
    rows = query_rows(
        d1_client,
        f"""
        SELECT title, link, source_name, doi, published_at,
               COALESCE(NULLIF(first_seen_at, ''), created_at) AS first_seen_at,
               COALESCE(NULLIF(last_seen_at, ''), created_at) AS last_seen_at,
               created_at
        FROM {D1_TABLE}
        ORDER BY datetime(COALESCE(NULLIF(last_seen_at, ''), created_at)) DESC
        LIMIT ?
        """,
        [limit],
    )

    deduped = {}
    for row in rows:
        identity = build_article_identity(row.get('title'), row.get('link'), row.get('doi'), row.get('source_name'))
        current = deduped.get(identity['dedupe_key'])
        if current is None:
            deduped[identity['dedupe_key']] = {
                'identity': identity,
                'first_seen_at': str(row.get('first_seen_at') or row.get('created_at') or '').strip(),
                'last_seen_at': str(row.get('last_seen_at') or row.get('created_at') or '').strip(),
                'published_at': str(row.get('published_at') or '').strip(),
            }
            continue

        current['first_seen_at'] = min(
            [item for item in [current['first_seen_at'], str(row.get('first_seen_at') or row.get('created_at') or '').strip()] if item],
            default=current['first_seen_at'],
        )
        current['last_seen_at'] = max(
            current['last_seen_at'],
            str(row.get('last_seen_at') or row.get('created_at') or '').strip(),
        )
        if not current['published_at']:
            current['published_at'] = str(row.get('published_at') or '').strip()

    synced = 0
    for item in deduped.values():
        res = upsert_article_state(
            d1_client,
            item['identity'],
            first_seen_at=item['first_seen_at'],
            last_seen_at=item['last_seen_at'],
            published_at=item['published_at'],
        )
        if res.get('success'):
            synced += 1

    return {'scanned': len(rows), 'synced': synced, 'unique': len(deduped)}


def build_ingest_batch_id(now=None):
    current = now or datetime.now(UTC)
    return f"paper_ingest_{current.strftime('%Y%m%dT%H%M%S%fZ')}"


def backfill_legacy_finalized_rows(d1_client):
    cutoff = f'-{LEGACY_FINALIZE_DELAY_MINUTES} minutes'
    count_rows = query_rows(
        d1_client,
        "SELECT COUNT(*) AS cnt FROM articles WHERE COALESCE(ingest_finalized_at, '') = '' AND datetime(created_at) <= datetime('now', ?)",
        [cutoff],
    )
    pending = int((count_rows[0] if count_rows else {}).get('cnt', 0) or 0)
    if pending <= 0:
        return {'updated': 0, 'stableDelayMinutes': LEGACY_FINALIZE_DELAY_MINUTES}

    d1_client.query(
        """
        UPDATE articles
        SET ingest_batch_id = COALESCE(NULLIF(ingest_batch_id, ''), 'legacy'),
                        ingest_finalized_at = COALESCE(NULLIF(ingest_finalized_at, ''), created_at),
                        first_seen_at = COALESCE(NULLIF(first_seen_at, ''), created_at),
                        last_seen_at = COALESCE(NULLIF(last_seen_at, ''), created_at)
        WHERE COALESCE(ingest_finalized_at, '') = ''
          AND datetime(created_at) <= datetime('now', ?)
        """,
        [cutoff],
    )
    return {'updated': pending, 'stableDelayMinutes': LEGACY_FINALIZE_DELAY_MINUTES}


def cleanup_stale_inflight_rows(d1_client):
    cutoff = f'-{INGEST_STALE_HOURS} hours'
    count_rows = query_rows(
        d1_client,
        "SELECT COUNT(*) AS cnt FROM articles WHERE COALESCE(ingest_finalized_at, '') = '' AND COALESCE(ingest_batch_id, '') != '' AND datetime(created_at) <= datetime('now', ?)",
        [cutoff],
    )
    stale_rows = int((count_rows[0] if count_rows else {}).get('cnt', 0) or 0)
    if stale_rows <= 0:
        return {'deleted': 0, 'staleHours': INGEST_STALE_HOURS}

    d1_client.query(
        "DELETE FROM articles WHERE COALESCE(ingest_finalized_at, '') = '' AND COALESCE(ingest_batch_id, '') != '' AND datetime(created_at) <= datetime('now', ?)",
        [cutoff],
    )
    return {'deleted': stale_rows, 'staleHours': INGEST_STALE_HOURS}


def finalize_ingest_batch(d1_client, batch_id):
    count_rows = query_rows(
        d1_client,
        "SELECT COUNT(*) AS cnt FROM articles WHERE ingest_batch_id = ? AND COALESCE(ingest_finalized_at, '') = ''",
        [batch_id],
    )
    row_count = int((count_rows[0] if count_rows else {}).get('cnt', 0) or 0)
    finalized_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    if row_count > 0:
        d1_client.query(
            "UPDATE articles SET ingest_finalized_at = ? WHERE ingest_batch_id = ? AND COALESCE(ingest_finalized_at, '') = ''",
            [finalized_at, batch_id],
        )
    return {'batchId': batch_id, 'rowCount': row_count, 'finalizedAt': finalized_at}

def get_feeds():
    """
    Get feeds list. 
    """
    feeds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'feeds.json')
    if not os.path.exists(feeds_path):
        print(f"Error: {feeds_path} not found.")
        return []
    
    with open(feeds_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_keyword_pool():
    keywords = []
    for key in ('chn', 'eng'):
        raw = config.get('paper.keywords', key, fallback='') or ''
        keywords.extend([item.strip() for item in raw.split(',') if item.strip()])
    deduped = []
    seen = set()
    for keyword in keywords:
        token = keyword.lower()
        if token in seen:
            continue
        seen.add(token)
        deduped.append(keyword)
    return deduped


def normalize_source_name(value):
    text = str(value or '').strip()
    if not text:
        return '未命名来源'

    upper_words = {'ieee', 'optica', 'mdpi', 'aps', 'osa', 'iop', 'oa', 'rss'}
    small_words = {'a', 'an', 'the', 'and', 'or', 'for', 'of', 'in', 'on', 'to', 'with'}
    words = [part for part in re.split(r'\s+', text) if part]
    formatted = []
    for idx, word in enumerate(words):
        lower = word.lower()
        if re.match(r'^[\u4e00-\u9fff]', word):
            formatted.append(word)
        elif lower in upper_words:
            formatted.append(lower.upper())
        elif 0 < idx < len(words) - 1 and lower in small_words:
            formatted.append(lower)
        elif re.match(r'^[A-Za-z]', word):
            formatted.append(word[:1].upper() + word[1:].lower())
        else:
            formatted.append(word)
    return ' '.join(formatted)


def strip_html_text(value):
    text = str(value or '')
    text = re.sub(r'<script[\s\S]*?</script>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<style[\s\S]*?</style>', ' ', text, flags=re.IGNORECASE)
    text = re.sub(r'<\s*br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</(p|div|section|article|h\d|li|ul|ol|tr)>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<(li|ul|ol)[^>]*>', ' ', text, flags=re.IGNORECASE)
    text = TAG_RE.sub(' ', text)
    text = html.unescape(text)
    text = text.replace('\r', '')
    text = re.sub(r'[^\S\n]+', ' ', text)
    text = re.sub(r' *\n+ *', '\n', text)
    text = re.sub(r'\n{3,}', '\n\n', text)
    return text.strip()


def normalize_url(value, base=''):
    raw = str(value or '').strip()
    if not raw:
        return ''
    if raw.startswith('//'):
        return f'https:{raw}'
    if raw.startswith('http://') or raw.startswith('https://'):
        return raw
    if base and (base.startswith('http://') or base.startswith('https://')):
        if raw.startswith('/'):
            match = re.match(r'^(https?://[^/]+)', base)
            return f"{match.group(1)}{raw}" if match else raw
        return f"{base.rstrip('/')}/{raw.lstrip('/')}"
    return raw


def extract_image_url(content, link=''):
    html_text = str(content or '')
    patterns = [
        r'<img[^>]+src\s*=\s*["\']([^"\']+)["\']',
        r'<meta[^>]+property\s*=\s*["\']og:image["\'][^>]+content\s*=\s*["\']([^"\']+)["\']',
        r'<meta[^>]+content\s*=\s*["\']([^"\']+)["\'][^>]+property\s*=\s*["\']og:image["\']'
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match:
            return normalize_url(match.group(1), link)
    return ''


def clean_authors_text(value):
    text = strip_html_text(value)
    text = re.sub(r'^(authors?|by|作者)\s*[:：\-]?\s*', '', text, flags=re.IGNORECASE)
    return text.strip()


def extract_authors_text(row):
    direct = clean_authors_text(row.get('authors') or row.get('author') or '')
    if direct:
        return direct

    html_text = str(row.get('content') or '')
    candidates = [
        re.search(r'(?:^|>|\n)\s*(?:authors?|by|作者)\s*[:：\-]?\s*([^<\n]{3,220})', html_text, flags=re.IGNORECASE),
        re.search(r'<strong>\s*(?:authors?|作者)\s*</strong>\s*[:：\-]?\s*([^<\n]{3,220})', html_text, flags=re.IGNORECASE),
        re.search(r'<p[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([\s\S]*?)</p>', html_text, flags=re.IGNORECASE),
    ]
    for candidate in candidates:
        if candidate and candidate.group(1):
            cleaned = clean_authors_text(candidate.group(1))
            if cleaned:
                return cleaned
    return ''


def split_authors(value):
    seen = set()
    authors = []
    for item in re.split(r'(?:,|;|，|；|、|\band\b|\s&\s)', clean_authors_text(value), flags=re.IGNORECASE):
        token = item.strip()
        if not token or len(token) > 80 or re.match(r'^et\.?\s*al\.?$', token, flags=re.IGNORECASE):
            continue
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        authors.append(token)
    return authors


def extract_doi(row):
    candidates = [
        str(row.get('doi') or ''),
        str(row.get('link') or ''),
        str(row.get('content') or ''),
        str(row.get('title') or '')
    ]
    for candidate in candidates:
        doi = normalize_doi(html.unescape(candidate))
        if doi:
            return doi
    return ''


def extract_volume_issue(link=''):
    link_text = str(link or '').strip()
    if not link_text:
        return {'volume': '', 'issue': ''}

    optica_match = re.search(r'(?:URI=|/abstract\.cfm\?URI=)[a-z0-9-]*?(\d+)-(\d+)-', link_text, flags=re.IGNORECASE)
    if not optica_match:
        optica_match = re.search(r'\b[a-z]{1,6}-(\d+)-(\d+)-', link_text, flags=re.IGNORECASE)

    if not optica_match:
        return {'volume': '', 'issue': ''}

    return {
        'volume': str(optica_match.group(1) or '').strip(),
        'issue': str(optica_match.group(2) or '').strip(),
    }


def normalize_crossref_abstract(value=''):
    return strip_html_text(re.sub(r'</?jats:[^>]+>', ' ', str(value or ''), flags=re.IGNORECASE)).strip()


def get_crossref_published_date(message=None):
    message = message or {}
    candidates = [
        message.get('published-print'),
        message.get('published-online'),
        message.get('published'),
        message.get('issued'),
        message.get('created'),
    ]

    for candidate in candidates:
        parts = candidate.get('date-parts', [None])[0] if isinstance(candidate, dict) else None
        if not isinstance(parts, list) or not parts:
            continue
        year = int(parts[0] or 0)
        month = int(parts[1] or 1) if len(parts) > 1 else 1
        day = int(parts[2] or 1) if len(parts) > 2 else 1
        if not year:
            continue
        return f'{year:04d}-{month:02d}-{day:02d}'

    return ''


def normalize_crossref_message(message=None):
    message = message or {}
    if not isinstance(message, dict):
        return None

    title_values = message.get('title')
    title = str(title_values[0] if isinstance(title_values, list) and title_values else title_values or '').strip()
    container_title = message.get('container-title') or message.get('journal') or ''
    journal = str(container_title[0] if isinstance(container_title, list) and container_title else container_title or '').strip()
    authors = []
    for entry in message.get('author') or []:
        author_name = ' '.join(part for part in [str(entry.get('given') or '').strip(), str(entry.get('family') or '').strip()] if part).strip()
        if author_name:
            authors.append(author_name)

    if not authors:
        for entry in message.get('authors') or []:
            token = str(entry or '').strip()
            if token:
                authors.append(token)

    doi = normalize_doi(message.get('DOI') or message.get('doi') or '')
    abstract = normalize_crossref_abstract(message.get('abstract') or '')
    url = str(message.get('URL') or message.get('url') or '').strip()
    volume = str(message.get('volume') or '').strip()
    issue = str(message.get('issue') or '').strip()
    pages = str(message.get('page') or '').strip()
    published_at = get_crossref_published_date(message) or str(message.get('publishedAt') or '').strip()

    if not any([doi, title, journal, abstract, url]):
        return None

    return {
        'doi': doi,
        'title': title,
        'journal': journal,
        'authors': authors,
        'authors_text': ', '.join(authors),
        'abstract': abstract,
        'url': url,
        'volume': volume,
        'issue': issue,
        'pages': pages,
        'published_at': published_at,
    }


def normalize_crossref_comparable_text(value=''):
    return re.sub(r'\s+', ' ', re.sub(r'[^a-z0-9\u4e00-\u9fff]+', ' ', strip_html_text(value).lower().replace('&', ' and '))).strip()


def build_crossref_token_set(value=''):
    return {token for token in normalize_crossref_comparable_text(value).split(' ') if len(token) > 1}


def extract_comparable_year(value=''):
    match = re.search(r'\b(19|20)\d{2}\b', str(value or ''))
    return int(match.group(0)) if match else 0


def score_crossref_search_candidate(item, candidate):
    item_title = normalize_crossref_comparable_text(item.get('title') or '')
    candidate_title = normalize_crossref_comparable_text(candidate.get('title') or '')
    if not item_title or not candidate_title:
        return -1

    score = 0.0
    if item_title == candidate_title:
        score += 120
    if candidate_title in item_title or item_title in candidate_title:
        score += 72

    item_tokens = build_crossref_token_set(item_title)
    candidate_tokens = build_crossref_token_set(candidate_title)
    overlap = len(item_tokens & candidate_tokens)
    if item_tokens:
        score += (overlap / len(item_tokens)) * 42
    score += overlap * 6

    item_journal = normalize_crossref_comparable_text(item.get('journal') or item.get('journalRaw') or '')
    candidate_journal = normalize_crossref_comparable_text(candidate.get('journal') or '')
    if item_journal and candidate_journal:
        if item_journal == candidate_journal:
            score += 22
        elif item_journal in candidate_journal or candidate_journal in item_journal:
            score += 10

    item_authors = item.get('authors') or split_authors(item.get('authors_text') or item.get('authorsText') or '')
    candidate_authors = candidate.get('authors') or split_authors(candidate.get('authors_text') or '')
    item_author = normalize_crossref_comparable_text(item_authors[0] if item_authors else '')
    candidate_author = normalize_crossref_comparable_text(candidate_authors[0] if candidate_authors else '')
    if item_author and candidate_author and (item_author in candidate_author or candidate_author in item_author):
        score += 14

    item_year = extract_comparable_year(item.get('published_at') or item.get('publishedAt') or item.get('created_at') or item.get('createdAt') or '')
    candidate_year = extract_comparable_year(candidate.get('published_at') or candidate.get('publishedAt') or '')
    if item_year and candidate_year:
        diff = abs(item_year - candidate_year)
        if diff == 0:
            score += 12
        elif diff == 1:
            score += 6
        elif diff <= 2:
            score += 2
        else:
            score -= 8

    if not candidate.get('doi'):
        score -= 40

    return score


def fetch_crossref_metadata(doi=''):
    normalized_doi = normalize_doi(doi)
    if not normalized_doi:
        return None

    params = {'mailto': CROSSREF_MAILTO} if CROSSREF_MAILTO else None
    payload = fetch_crossref_json(
        f'{CROSSREF_BASE}{requests.utils.quote(normalized_doi, safe="")}',
        params=params,
    )
    if not payload:
        return None

    return normalize_crossref_message(payload.get('message') if isinstance(payload, dict) else None)


def search_crossref_metadata(item):
    title = str(item.get('title') or '').strip()
    if len(title) < 8:
        return None

    query_parts = [
        title,
        str(item.get('journal') or item.get('journalRaw') or '').strip(),
        ' '.join((item.get('authors') or split_authors(item.get('authors_text') or item.get('authorsText') or ''))[:2]),
        str(item.get('published_at') or item.get('publishedAt') or '')[:4],
    ]
    params = {
        'query.bibliographic': ' '.join(part for part in query_parts if part),
        'rows': CROSSREF_SEARCH_ROWS,
    }
    if CROSSREF_MAILTO:
        params['mailto'] = CROSSREF_MAILTO

    payload = fetch_crossref_json(CROSSREF_SEARCH_BASE, params=params)
    if not payload:
        return None

    best_match = None
    best_score = -1
    for entry in ((payload.get('message') or {}).get('items') or []):
        candidate = normalize_crossref_message(entry)
        if not candidate:
            continue
        score = score_crossref_search_candidate(item, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match if best_score >= 56 else None


def search_crossref_exact_title_metadata(item):
    title = str(item.get('title') or '').strip()
    if len(title) < 8:
        return None

    params = {
        'query.title': title,
        'rows': CROSSREF_TITLE_ROWS,
    }
    if CROSSREF_MAILTO:
        params['mailto'] = CROSSREF_MAILTO

    payload = fetch_crossref_json(CROSSREF_SEARCH_BASE, params=params)
    if not payload:
        return None

    best_match = None
    best_score = -1
    for entry in ((payload.get('message') or {}).get('items') or []):
        candidate = normalize_crossref_message(entry)
        if not candidate:
            continue
        score = score_crossref_search_candidate(item, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate

    return best_match if best_score >= 48 else None


def resolve_crossref_metadata(item):
    by_doi = fetch_crossref_metadata(item.get('doi') or '')
    if by_doi:
        return by_doi
    by_search = search_crossref_metadata(item)
    if by_search:
        return by_search
    return search_crossref_exact_title_metadata(item)


def extract_entry_text(entry, key):
    value = entry.get(key) if hasattr(entry, 'get') else getattr(entry, key, '')
    if isinstance(value, list) and value:
      candidate = value[0]
      if isinstance(candidate, dict):
        return str(candidate.get('value') or candidate.get('content') or '').strip()
      return str(candidate or '').strip()
    if isinstance(value, dict):
      return str(value.get('value') or value.get('content') or '').strip()
    return str(value or '').strip()


def extract_entry_authors(entry):
    authors = []
    if hasattr(entry, 'get'):
        author_entries = entry.get('authors') or []
        for item in author_entries:
            if isinstance(item, dict):
                name = str(item.get('name') or '').strip()
                if name:
                    authors.append(name)

    fallback_candidates = [
        extract_entry_text(entry, 'author'),
        extract_entry_text(entry, 'dc_creator'),
        extract_entry_text(entry, 'creator')
    ]
    for candidate in fallback_candidates:
        if candidate:
            authors.extend(split_authors(candidate) or [candidate])

    deduped = []
    seen = set()
    for item in authors:
        token = str(item or '').strip()
        if not token:
            continue
        lowered = token.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        deduped.append(token)
    return ', '.join(deduped[:12])


def extract_entry_doi(entry):
    candidates = [
        extract_entry_text(entry, 'doi'),
        extract_entry_text(entry, 'prism_doi'),
        extract_entry_text(entry, 'dc_identifier'),
        extract_entry_text(entry, 'identifier'),
        extract_entry_text(entry, 'id'),
        extract_entry_text(entry, 'link'),
        extract_entry_text(entry, 'summary'),
        extract_entry_text(entry, 'description'),
        extract_entry_text(entry, 'title')
    ]
    for candidate in candidates:
        doi = normalize_doi(html.unescape(candidate))
        if doi:
            return doi
    return ''


def extract_entry_content(entry):
    for key in ('content', 'summary', 'description', 'summary_detail', 'subtitle'):
        text = extract_entry_text(entry, key)
        if text:
            return text
    return ''


def build_article_content(body='', doi='', authors='', volume='', issue='', pages=''):
    content_body = str(body or '').strip()
    prefix_parts = []
    authors_text = clean_authors_text(authors)
    doi_text = normalize_doi(doi)
    if authors_text:
        prefix_parts.append(f'<p>Authors: {html.escape(authors_text)}</p>')
    if doi_text:
        prefix_parts.append(f'<p>DOI: {html.escape(doi_text)}</p>')

    citation_bits = []
    if str(volume or '').strip():
        citation_bits.append(f'Vol. {str(volume).strip()}')
    if str(issue or '').strip():
        citation_bits.append(f'Issue {str(issue).strip()}')
    if str(pages or '').strip():
        citation_bits.append(f'Pages {str(pages).strip()}')
    if citation_bits:
        prefix_parts.append(f'<p>Citation: {html.escape(", ".join(citation_bits))}</p>')

    if content_body:
        prefix_parts.append(content_body)
    return ''.join(prefix_parts)


def build_entry_content(entry, link=''):
    body = extract_entry_content(entry)
    doi = extract_entry_doi(entry)
    authors = extract_entry_authors(entry)
    volume_issue = extract_volume_issue(link)
    metadata_source = merge_metadata_sources('feed')
    if link and (not doi or not strip_html_text(body) or not authors):
        article_meta = fetch_article_metadata(link)
        if not doi:
            doi = normalize_doi(article_meta.get('doi') or '')
        if not authors:
            authors = article_meta.get('authors') or ''
        if not strip_html_text(body) and article_meta.get('abstract'):
            body = f'<p>{html.escape(article_meta["abstract"])}</p>'
        metadata_source = merge_metadata_sources(metadata_source, 'page')
    content = build_article_content(body, doi=doi, authors=authors, volume=volume_issue['volume'], issue=volume_issue['issue'])
    return {
        'content': content,
        'doi': normalize_doi(doi),
        'authors': clean_authors_text(authors),
        'volume': volume_issue['volume'],
        'issue': volume_issue['issue'],
        'pages': '',
        'metadata_source': metadata_source,
    }


def build_crossref_enrichment_item(row):
    authors_text = clean_authors_text(row.get('authors') or extract_authors_text(row) or '')
    return {
        'id': str(row.get('id') or '').strip(),
        'title': str(row.get('title') or '').strip(),
        'journal': str(row.get('source_name') or '').strip(),
        'journalRaw': str(row.get('source_name') or '').strip(),
        'link': str(row.get('link') or '').strip(),
        'published_at': str(row.get('published_at') or '').strip(),
        'created_at': str(row.get('created_at') or '').strip(),
        'doi': normalize_doi(row.get('doi') or extract_doi(row)),
        'authors': split_authors(authors_text),
        'authors_text': authors_text,
        'volume': str(row.get('volume') or '').strip(),
        'issue': str(row.get('issue') or '').strip(),
        'pages': str(row.get('pages') or '').strip(),
        'metadata_source': str(row.get('metadata_source') or '').strip(),
        'content': str(row.get('content') or '').strip(),
    }


def needs_crossref_enrichment(item):
    return not item.get('doi')


def backfill_recent_embedded_metadata(d1_client, lookback_hours=None, limit=400):
    effective_hours = lookback_hours or CROSSREF_LOOKBACK_HOURS
    rows = query_rows(
        d1_client,
        f"""
        SELECT id, title, link, published_at, created_at, source_name, source_type, content,
               doi, authors, volume, issue, pages, metadata_source
        FROM articles
        WHERE created_at > datetime('now', ?)
          AND source_type = 'journal'
          AND (
              COALESCE(doi, '') = ''
              OR COALESCE(authors, '') = ''
              OR COALESCE(volume, '') = ''
              OR COALESCE(issue, '') = ''
          )
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [f'-{effective_hours} hours', limit],
    )

    summary = {
        'generatedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'lookbackHours': effective_hours,
        'limit': limit,
        'scanned': len(rows),
        'updated': 0,
        'doiFilled': 0,
        'examples': [],
    }

    for row in rows:
        update_fields = {}
        parsed_doi = normalize_doi(row.get('doi') or extract_doi(row))
        parsed_authors = clean_authors_text(row.get('authors') or extract_authors_text(row) or '')
        parsed_volume_issue = extract_volume_issue(row.get('link') or '')

        if parsed_doi and not str(row.get('doi') or '').strip():
            update_fields['doi'] = parsed_doi
            summary['doiFilled'] += 1
        if parsed_authors and not str(row.get('authors') or '').strip():
            update_fields['authors'] = parsed_authors
        if parsed_volume_issue['volume'] and not str(row.get('volume') or '').strip():
            update_fields['volume'] = parsed_volume_issue['volume']
        if parsed_volume_issue['issue'] and not str(row.get('issue') or '').strip():
            update_fields['issue'] = parsed_volume_issue['issue']

        merged_source = merge_metadata_sources(row.get('metadata_source'), 'embedded')
        if update_fields and merged_source != str(row.get('metadata_source') or '').strip():
            update_fields['metadata_source'] = merged_source

        if not update_fields:
            continue

        assignments = ', '.join(f"{field} = ?" for field in update_fields)
        params = list(update_fields.values()) + [row['id']]
        result = d1_client.query(f'UPDATE articles SET {assignments} WHERE id = ?', params)
        if not result.get('success'):
            continue

        summary['updated'] += 1
        if len(summary['examples']) < 12:
            summary['examples'].append({
                'title': row.get('title'),
                'source': row.get('source_name'),
                'doi': update_fields.get('doi') or '',
            })

    return summary


def enrich_recent_articles_with_crossref(d1_client, lookback_hours=None, limit=None):
    if CROSSREF_MAX_ENRICH_PER_RUN <= 0 and limit is None:
        return {
            'generatedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'lookbackHours': lookback_hours or CROSSREF_LOOKBACK_HOURS,
            'limit': 0,
            'candidates': 0,
            'matched': 0,
            'updated': 0,
            'doiFilled': 0,
            'examples': [],
            'errors': [],
        }

    effective_hours = lookback_hours or CROSSREF_LOOKBACK_HOURS
    effective_limit = limit or CROSSREF_MAX_ENRICH_PER_RUN
    rows = query_rows(
        d1_client,
        f"""
        SELECT id, title, link, published_at, created_at, source_name, source_type, content,
               doi, authors, volume, issue, pages, metadata_source
        FROM articles
        WHERE created_at > datetime('now', ?)
          AND source_type = 'journal'
                    AND COALESCE(doi, '') = ''
        ORDER BY created_at DESC
        LIMIT ?
        """,
        [f'-{effective_hours} hours', effective_limit],
    )

    candidates = [build_crossref_enrichment_item(row) for row in rows]
    candidates = [item for item in candidates if needs_crossref_enrichment(item)]

    summary = {
        'generatedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'lookbackHours': effective_hours,
        'limit': effective_limit,
        'candidates': len(candidates),
        'matched': 0,
        'updated': 0,
        'doiFilled': 0,
        'examples': [],
        'errors': [],
    }

    if not candidates:
        return summary

    resolved = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(6, len(candidates))) as executor:
        future_to_item = {executor.submit(resolve_crossref_metadata, item): item for item in candidates}
        for future in concurrent.futures.as_completed(future_to_item):
            item = future_to_item[future]
            try:
                resolved.append((item, future.result()))
            except Exception as exc:
                summary['errors'].append({
                    'id': item['id'],
                    'title': item['title'],
                    'error': str(exc),
                })

    for item, crossref in resolved:
        if not crossref:
            continue

        summary['matched'] += 1
        next_doi = item['doi'] or crossref.get('doi') or ''
        next_authors = item['authors_text'] or crossref.get('authors_text') or ''
        next_volume = item['volume'] or crossref.get('volume') or ''
        next_issue = item['issue'] or crossref.get('issue') or ''
        next_pages = item['pages'] or crossref.get('pages') or ''
        update_fields = {}

        if next_doi and next_doi != item['doi']:
            update_fields['doi'] = next_doi
            summary['doiFilled'] += 1
        if next_authors and next_authors != item['authors_text']:
            update_fields['authors'] = next_authors
        if next_volume and next_volume != item['volume']:
            update_fields['volume'] = next_volume
        if next_issue and next_issue != item['issue']:
            update_fields['issue'] = next_issue
        if next_pages and next_pages != item['pages']:
            update_fields['pages'] = next_pages

        merged_source = merge_metadata_sources(item.get('metadata_source'), 'crossref')
        if merged_source and merged_source != item.get('metadata_source'):
            update_fields['metadata_source'] = merged_source

        if not update_fields:
            continue

        update_fields['crossref_updated_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        assignments = ', '.join(f"{field} = ?" for field in update_fields)
        params = list(update_fields.values()) + [item['id']]
        result = d1_client.query(f'UPDATE articles SET {assignments} WHERE id = ?', params)
        if not result.get('success'):
            summary['errors'].append({
                'id': item['id'],
                'title': item['title'],
                'error': result.get('error') or 'update failed',
            })
            continue

        summary['updated'] += 1
        if len(summary['examples']) < 12:
            summary['examples'].append({
                'title': item['title'],
                'source': item['journal'],
                'doi': update_fields.get('doi') or item['doi'] or crossref.get('doi') or '',
                'metadataSource': update_fields.get('metadata_source') or item.get('metadata_source') or 'crossref',
            })

    return summary


def extract_page_doi(html_text):
    candidates = []
    patterns = [
        r'<meta[^>]+name=["\']citation_doi["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_doi["\']',
        r'<meta[^>]+name=["\']dc\.identifier["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']dc\.identifier["\']',
        r'<meta[^>]+name=["\']prism\.doi["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']prism\.doi["\']',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match and match.group(1):
            candidates.append(match.group(1))

    candidates.append(html_text)
    for candidate in candidates:
        match = DOI_PATTERN.search(html.unescape(candidate or ''))
        if match:
            return match.group(1).rstrip(').,;]')
    return ''


def extract_page_abstract(html_text):
    patterns = [
        r'<meta[^>]+name=["\']citation_abstract["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_abstract["\']',
        r'<meta[^>]+name=["\']dc\.description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']dc\.description["\']',
        r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']description["\']',
        r'<section[^>]*class=["\'][^"\']*abstract[^"\']*["\'][^>]*>([\s\S]*?)</section>',
        r'<div[^>]*class=["\'][^"\']*abstract[^"\']*["\'][^>]*>([\s\S]*?)</div>',
    ]
    for pattern in patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if not match or not match.group(1):
            continue
        text = strip_html_text(match.group(1))
        if text and len(text) >= 40:
            return text
    return ''


def extract_page_authors(html_text):
    candidates = []
    meta_patterns = [
        r'<meta[^>]+name=["\']citation_author["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']citation_author["\']',
        r'<meta[^>]+name=["\']dc\.creator["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']dc\.creator["\']',
        r'<meta[^>]+name=["\']author["\'][^>]+content=["\']([^"\']+)["\']',
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+name=["\']author["\']',
    ]
    block_patterns = [
        r'<p[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([\s\S]*?)</p>',
        r'<div[^>]*class=["\'][^"\']*author[^"\']*["\'][^>]*>([\s\S]*?)</div>',
        r'(?:^|>|\n)\s*(?:authors?|by|作者)\s*[:：\-]?\s*([^<\n]{3,220})',
    ]

    for pattern in meta_patterns:
        candidates.extend(re.findall(pattern, html_text, flags=re.IGNORECASE))

    for pattern in block_patterns:
        match = re.search(pattern, html_text, flags=re.IGNORECASE)
        if match and match.group(1):
            candidates.append(match.group(1))

    authors = []
    seen = set()
    for candidate in candidates:
        cleaned = clean_authors_text(candidate)
        if not cleaned:
            continue
        for item in split_authors(cleaned) or [cleaned]:
            lowered = item.lower()
            if lowered in seen:
                continue
            seen.add(lowered)
            authors.append(item)

    return ', '.join(authors)


def fetch_article_metadata(link):
    normalized_link = normalize_url(link)
    if not normalized_link:
        return {'doi': '', 'abstract': '', 'authors': ''}
    if normalized_link in ARTICLE_META_CACHE:
        return ARTICLE_META_CACHE[normalized_link]

    result = {'doi': '', 'abstract': '', 'authors': ''}
    try:
        response = requests.get(normalized_link, timeout=20, headers={
            'User-Agent': 'Mozilla/5.0 (GitHub Actions; Cloud Native Fetcher)'
        })
        if response.status_code == 200:
            html_text = response.text[:220000]
            result = {
                'doi': extract_page_doi(html_text),
                'abstract': extract_page_abstract(html_text),
                'authors': extract_page_authors(html_text)
            }
    except Exception:
        result = {'doi': '', 'abstract': '', 'authors': ''}

    ARTICLE_META_CACHE[normalized_link] = result
    return result


def match_keywords(title, abstract, keywords):
    haystack = f"{title} {abstract}".lower()
    matched = []
    for keyword in keywords:
        token = keyword.lower()
        if token and token in haystack:
            matched.append(keyword)
    return matched[:8]


def normalize_snapshot_row(row, keywords):
    link = normalize_url(row.get('link') or '')
    abstract = strip_html_text(row.get('content') or '') or '暂无摘要'
    authors_text = extract_authors_text(row)
    display_date = str(row.get('published_at') or row.get('created_at') or '').strip()
    title = str(row.get('title') or '未命名文章').strip() or '未命名文章'
    doi = normalize_doi(row.get('doi') or extract_doi(row))
    volume = str(row.get('volume') or '').strip()
    issue = str(row.get('issue') or '').strip()
    pages = str(row.get('pages') or '').strip()
    metadata_source = str(row.get('metadata_source') or '').strip()

    if link and (not authors_text or not doi or abstract == '暂无摘要'):
        article_meta = fetch_article_metadata(link)
        if not authors_text:
            authors_text = clean_authors_text(article_meta.get('authors') or '')
        if not doi:
            doi = article_meta.get('doi') or ''
        if abstract == '暂无摘要' and article_meta.get('abstract'):
            abstract = article_meta.get('abstract')

    keyword_hits = match_keywords(title, abstract, keywords)

    return {
        'id': str(row.get('id') or row.get('link') or row.get('title') or '').strip(),
        'title': title,
        'link': link,
        'journal': normalize_source_name(row.get('source_name') or ''),
        'journalRaw': str(row.get('source_name') or '').strip(),
        'sourceType': str(row.get('source_type') or 'journal').strip() or 'journal',
        'publishedAt': str(row.get('published_at') or '').strip(),
        'createdAt': str(row.get('created_at') or '').strip(),
        'displayDate': display_date,
        'dateKey': display_date[:10] if display_date else '',
        'abstract': abstract,
        'excerpt': abstract[:220].strip() + '...' if len(abstract) > 220 else abstract,
        'authors': split_authors(authors_text),
        'authorsText': authors_text,
        'imageUrl': extract_image_url(row.get('content') or '', link),
        'doi': doi,
        'volume': volume,
        'issue': issue,
        'pages': pages,
        'metadataSource': metadata_source,
        'keywords': keyword_hits
    }


def build_optics_snapshot(d1_client):
    rows = query_rows(
        d1_client,
        """
                SELECT id, title, link, published_at, created_at, source_name, source_type, content,
                             doi, authors, volume, issue, pages, metadata_source
        FROM articles
        WHERE source_type = ?
                    AND COALESCE(ingest_finalized_at, '') != ''
          AND datetime(COALESCE(NULLIF(published_at, ''), created_at)) >= datetime('now', ?)
        ORDER BY datetime(COALESCE(NULLIF(published_at, ''), created_at)) DESC, datetime(created_at) DESC
        LIMIT ?
        """,
        ['journal', f'-{SNAPSHOT_RETENTION_DAYS} days', SNAPSHOT_MAX_ITEMS]
    )

    keyword_pool = get_keyword_pool()
    items = []
    journal_counts = {}
    for row in rows:
        item = normalize_snapshot_row(row, keyword_pool)
        if not item['id'] or not item['title']:
            continue
        items.append(item)
        journal_counts[item['journalRaw']] = journal_counts.get(item['journalRaw'], 0) + 1

    journals = [
        {
            'name': name,
            'label': normalize_source_name(name),
            'count': count,
        }
        for name, count in sorted(journal_counts.items(), key=lambda entry: entry[0].lower())
        if name
    ]

    snapshot = {
        'items': items,
        'journals': journals,
        'meta': {
            'total': len(items),
            'journalCount': len(journals),
            'generatedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
            'retentionDays': SNAPSHOT_RETENTION_DAYS,
            'limit': SNAPSHOT_MAX_ITEMS,
            'source': 'push-rss-d1'
        }
    }

    payload_text = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'))
    snapshot['meta']['etag'] = hashlib.md5(payload_text.encode('utf-8')).hexdigest()
    return snapshot


def save_snapshot_file(snapshot):
    out_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'output', 'paper')
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, 'optics_snapshot.json')
    with open(out_path, 'w', encoding='utf-8') as file_obj:
        json.dump(snapshot, file_obj, ensure_ascii=False, indent=2)
    return out_path


def export_optics_snapshot(snapshot, kv_client):
    payload_text = json.dumps(snapshot, ensure_ascii=False, separators=(',', ':'))
    if kv_client.enabled:
        result = kv_client.put(SNAPSHOT_OUTPUT_KEY, payload_text)
        if result.get('success'):
            print(f"Optics snapshot exported to KV key: {SNAPSHOT_OUTPUT_KEY}")
        else:
            print(f"Optics snapshot export skipped/failed: {result.get('error')}")
    else:
        print('Optics snapshot KV export skipped (KV client not configured).')

    out_path = save_snapshot_file(snapshot)
    print(f"Optics snapshot saved locally: {out_path}")

def fetch_feed(feed_url, max_retries=3):
    """Fetch a single feed with retries"""
    for attempt in range(max_retries):
        try:
            resp = requests.get(feed_url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (GitHub Actions; Cloud Native Fetcher)'
            })
            if resp.status_code == 200:
                parsed = feedparser.parse(resp.content)
                if not parsed.entries and parsed.bozo:
                    # Retry on Bozo error if maybe intermittent?
                    if attempt < max_retries - 1: continue
                return parsed
        except Exception as e:
            # print(f"Error fetching {feed_url}: {e}") # Reduce noise
            if attempt < max_retries - 1:
                import time
                time.sleep(2)
    return None

def process_feed_and_insert(feed, d1_client, batch_id=''):
    """Fetch specific feed and insert directly to minimize memory usage"""
    # Note: d1_client instance sharing across threads? 
    # d1_client uses requests.post, which is thread-safe? Yes usually.
    # But let's instantiate local client if needed? Or just pass it.
    
    print(f"Processing {feed['title']}...")
    parsed = fetch_feed(feed['url'])
    if not parsed:
        print(f"Failed to fetch {feed['title']}")
        return {
            'feed': feed['title'],
            'inserted': 0,
            'skipped_old': 0,
            'fetch_failed': True,
            'errors': [],
        }
        
    count = 0
    skipped_old = 0
    errors = []
    for entry in parsed.entries:
        try:
            # Parse Date
            dt = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                dt = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                dt = datetime(*entry.updated_parsed[:6])

            # 与 cleanup 保持一致：保留窗口之外的旧文章不再写入 D1，避免整点并发时被 paper 当成新 created_at 误推。
            if not is_entry_within_retention(dt):
                skipped_old += 1
                continue
            
            # Generate ID (Hash of link)
            link = entry.link
            aid = hashlib.md5(link.encode('utf-8')).hexdigest()
            title = entry.title
            seen_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            entry_payload = build_entry_content(entry, link)
            identity = build_article_identity(title, link, entry_payload['doi'], feed['title'])
            upsert_article_state(
                d1_client,
                identity,
                first_seen_at=seen_at,
                last_seen_at=seen_at,
                published_at=dt.strftime('%Y-%m-%d %H:%M:%S'),
            )
            
            # Article row keeps the earliest first_seen_at but refreshes last_seen_at on repeated RSS delivery.
            sql = """
            INSERT INTO articles (
                id, title, link, published_at, source_name, source_type, content, created_at,
                doi, authors, volume, issue, pages, metadata_source, crossref_updated_at,
                ingest_batch_id, ingest_finalized_at, first_seen_at, last_seen_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?,
                    COALESCE((SELECT first_seen_at FROM paper_article_state WHERE dedupe_key = ?), ?), ?)
            ON CONFLICT(id) DO UPDATE SET
                title = COALESCE(NULLIF(excluded.title, ''), articles.title),
                link = COALESCE(NULLIF(excluded.link, ''), articles.link),
                published_at = CASE
                    WHEN COALESCE(NULLIF(articles.published_at, ''), '') = '' THEN excluded.published_at
                    WHEN COALESCE(NULLIF(excluded.published_at, ''), '') = '' THEN articles.published_at
                    WHEN datetime(excluded.published_at) < datetime(articles.published_at) THEN excluded.published_at
                    ELSE articles.published_at
                END,
                source_name = COALESCE(NULLIF(excluded.source_name, ''), articles.source_name),
                source_type = COALESCE(NULLIF(excluded.source_type, ''), articles.source_type),
                content = CASE
                    WHEN LENGTH(COALESCE(excluded.content, '')) > LENGTH(COALESCE(articles.content, '')) THEN excluded.content
                    ELSE articles.content
                END,
                doi = COALESCE(NULLIF(articles.doi, ''), NULLIF(excluded.doi, ''), articles.doi),
                authors = COALESCE(NULLIF(articles.authors, ''), NULLIF(excluded.authors, ''), articles.authors),
                volume = COALESCE(NULLIF(articles.volume, ''), NULLIF(excluded.volume, ''), articles.volume),
                issue = COALESCE(NULLIF(articles.issue, ''), NULLIF(excluded.issue, ''), articles.issue),
                pages = COALESCE(NULLIF(articles.pages, ''), NULLIF(excluded.pages, ''), articles.pages),
                metadata_source = COALESCE(NULLIF(articles.metadata_source, ''), NULLIF(excluded.metadata_source, ''), articles.metadata_source),
                ingest_batch_id = excluded.ingest_batch_id,
                ingest_finalized_at = NULL,
                first_seen_at = CASE
                    WHEN COALESCE(NULLIF(articles.first_seen_at, ''), '') = '' THEN excluded.first_seen_at
                    WHEN COALESCE(NULLIF(excluded.first_seen_at, ''), '') = '' THEN articles.first_seen_at
                    WHEN datetime(excluded.first_seen_at) < datetime(articles.first_seen_at) THEN excluded.first_seen_at
                    ELSE articles.first_seen_at
                END,
                last_seen_at = COALESCE(NULLIF(excluded.last_seen_at, ''), articles.last_seen_at)
            """
            
            params = [
                aid, 
                title, 
                link, 
                dt.strftime('%Y-%m-%d %H:%M:%S'), 
                feed['title'], 
                feed.get('type', 'journal'), 
                entry_payload['content'][:16000], 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                entry_payload['doi'],
                entry_payload['authors'],
                entry_payload['volume'],
                entry_payload['issue'],
                entry_payload['pages'],
                entry_payload['metadata_source'],
                None,
                batch_id,
                None,
                identity['dedupe_key'],
                seen_at,
                seen_at,
            ]
            
            res = d1_client.query(sql, params)
            if res.get('success'):
                count += 1
            else:
                errors.append({
                    'title': title,
                    'error': res.get('error') or 'insert failed'
                })
        except Exception as e:
            print(f"Error processing entry {title}: {e}")
            errors.append({
                'title': title,
                'error': str(e)
            })
            
    return {
        'feed': feed['title'],
        'inserted': count,
        'skipped_old': skipped_old,
        'fetch_failed': False,
        'errors': errors[:10],
    }

def main():
    # 1. Initialize D1
    d1 = D1Client()
    if not d1.enabled:
        print("D1 Client not enabled. Check CLOUDFLARE_D1_* env vars.")
        sys.exit(1)

    # 2. Ensure Table Exists (Fast check)
    schema = """
    CREATE TABLE IF NOT EXISTS articles (
        id TEXT PRIMARY KEY,
        title TEXT,
        link TEXT,
        published_at TEXT,
        source_name TEXT,
        source_type TEXT,
        content TEXT,
        created_at TEXT,
        doi TEXT,
        authors TEXT,
        volume TEXT,
        issue TEXT,
        pages TEXT,
        metadata_source TEXT,
        crossref_updated_at TEXT,
        ingest_batch_id TEXT,
        ingest_finalized_at TEXT,
        first_seen_at TEXT,
        last_seen_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_published ON articles(published_at);
    CREATE INDEX IF NOT EXISTS idx_created ON articles(created_at);
    CREATE INDEX IF NOT EXISTS idx_source_created ON articles(source_name, created_at);
    CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);
    CREATE INDEX IF NOT EXISTS idx_articles_ingest_finalized ON articles(ingest_finalized_at);
    CREATE INDEX IF NOT EXISTS idx_articles_ingest_batch ON articles(ingest_batch_id);
    CREATE INDEX IF NOT EXISTS idx_articles_first_seen ON articles(first_seen_at);
    CREATE INDEX IF NOT EXISTS idx_articles_last_seen ON articles(last_seen_at);
    CREATE TABLE IF NOT EXISTS paper_article_state (
        dedupe_key TEXT PRIMARY KEY,
        dedupe_kind TEXT,
        source_name TEXT,
        title TEXT,
        link TEXT,
        doi TEXT,
        first_seen_at TEXT,
        last_seen_at TEXT,
        first_published_at TEXT,
        last_published_at TEXT,
        seen_count INTEGER DEFAULT 1,
        updated_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_article_state_first_seen ON paper_article_state(first_seen_at);
    CREATE INDEX IF NOT EXISTS idx_article_state_last_seen ON paper_article_state(last_seen_at);
    CREATE TABLE IF NOT EXISTS finance_tags (
        name TEXT PRIMARY KEY,
        url  TEXT,
        date TEXT
    );
    """
    d1.ensure_table(D1_TABLE, schema)
    ensure_articles_schema(d1)
    ensure_article_state_table(d1)
    article_seen_backfill_summary = backfill_article_seen_columns(d1)
    article_state_sync_summary = sync_article_state_from_articles(d1)
    stale_inflight_summary = cleanup_stale_inflight_rows(d1)
    legacy_finalize_summary = backfill_legacy_finalized_rows(d1)
    batch_id = build_ingest_batch_id()
    
    # 3. Fetch Feeds (Parallel)
    feeds = get_feeds()
    print(f"Fetching {len(feeds)} feeds in parallel...")
    
    total_new = 0
    total_skipped_old = 0
    per_feed_stats = []
    
    # Use ThreadPoolExecutor for I/O bound tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit tasks
        future_to_feed = {executor.submit(process_feed_and_insert, feed, d1, batch_id): feed for feed in feeds}
        
        for future in concurrent.futures.as_completed(future_to_feed):
            feed = future_to_feed[future]
            try:
                result = future.result()
                per_feed_stats.append(result)
                cnt = int(result.get('inserted', 0))
                skipped_old = int(result.get('skipped_old', 0))
                total_new += cnt
                total_skipped_old += skipped_old
                if cnt > 0 or skipped_old > 0:
                    print(f"[{feed['title']}] Inserted {cnt} articles, skipped old {skipped_old}.")
            except Exception as exc:
                print(f"[{feed['title']}] Generated an exception: {exc}")

    print(f"Total articles inserted/checked: {total_new}")
    print(f"Total old articles skipped before insert: {total_skipped_old}")

    # 4. Cleanup Old Data (Retention: 7 days)
    print("Cleaning up old articles...")
    d1.query("DELETE FROM articles WHERE datetime(COALESCE(NULLIF(first_seen_at, ''), created_at)) < datetime('now', ?)", [f'-{ARTICLE_RETENTION_DAYS} days'])

    # 5. Crossref sidecar enriches latest rows after RSS/page metadata are persisted.
    print('Backfilling embedded paper metadata...')
    embedded_summary = backfill_recent_embedded_metadata(d1)
    print(f"Embedded metadata updated: {embedded_summary['updated']} rows, DOI filled: {embedded_summary['doiFilled']}")

    print('Enriching recent articles with Crossref...')
    crossref_summary = enrich_recent_articles_with_crossref(d1)
    crossref_audit_path = write_crossref_audit(crossref_summary)
    print(f"Crossref updated: {crossref_summary['updated']} rows, DOI filled: {crossref_summary['doiFilled']}")
    print(f'Crossref audit saved: {crossref_audit_path}')

    print('Finalizing ingest batch...')
    finalize_summary = finalize_ingest_batch(d1, batch_id)
    print(f"Ingest batch finalized: {finalize_summary['rowCount']} rows at {finalize_summary['finalizedAt']}")

    # 6. Export optics snapshot (optional, but runs in the same hourly RSS task)
    print('Building optics snapshot...')
    snapshot = build_optics_snapshot(d1)
    kv_client = CloudflareKVClient()
    export_optics_snapshot(snapshot, kv_client)

    ingest_summary = {
        'generatedAt': datetime.now(UTC).strftime('%Y-%m-%dT%H:%M:%SZ'),
        'batchId': batch_id,
        'retentionDays': ARTICLE_RETENTION_DAYS,
        'feedsTotal': len(feeds),
        'insertedTotal': total_new,
        'skippedOldTotal': total_skipped_old,
        'articleSeenBackfill': article_seen_backfill_summary,
        'articleStateSync': article_state_sync_summary,
        'staleInflightCleanup': stale_inflight_summary,
        'legacyFinalizeBackfill': legacy_finalize_summary,
        'finalizedBatch': finalize_summary,
        'embeddedMetadata': embedded_summary,
        'crossref': crossref_summary,
        'perFeed': sorted(per_feed_stats, key=lambda item: str(item.get('feed', '')).lower())
    }
    audit_path = write_ingest_audit(ingest_summary)
    print(f'Ingest audit saved: {audit_path}')
    
    print("Done.")

if __name__ == "__main__":
    main()
