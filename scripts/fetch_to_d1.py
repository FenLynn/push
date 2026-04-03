import concurrent.futures
import hashlib
import html
import json
import os
import re
import sys
from datetime import datetime

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
SNAPSHOT_OUTPUT_KEY = os.getenv('OPTICS_SNAPSHOT_KV_KEY', 'dashboard:snapshot:optics:latest')
SNAPSHOT_MAX_ITEMS = max(200, int(os.getenv('PAPER_SNAPSHOT_MAX_ITEMS', '1200')))
SNAPSHOT_RETENTION_DAYS = max(1, int(os.getenv('PAPER_SNAPSHOT_RETENTION_DAYS', '7')))

DOI_PATTERN = re.compile(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', re.IGNORECASE)
TAG_RE = re.compile(r'<[^>]+>')


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
        match = DOI_PATTERN.search(html.unescape(candidate))
        if match:
            return match.group(1).rstrip(').,;]')
    return ''


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
        match = DOI_PATTERN.search(html.unescape(candidate))
        if match:
            return match.group(1).rstrip(').,;]')
    return ''


def extract_entry_content(entry):
    for key in ('content', 'summary', 'description', 'summary_detail', 'subtitle'):
        text = extract_entry_text(entry, key)
        if text:
            return text
    return ''


def build_entry_content(entry):
    body = extract_entry_content(entry)
    doi = extract_entry_doi(entry)
    authors = extract_entry_authors(entry)
    prefix_parts = []
    if authors:
        prefix_parts.append(f'<p>Authors: {html.escape(authors)}</p>')
    if doi:
        prefix_parts.append(f'<p>DOI: {html.escape(doi)}</p>')
    if body:
        prefix_parts.append(body)
    return ''.join(prefix_parts), doi, authors


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
    doi = extract_doi(row)
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
        'keywords': keyword_hits
    }


def build_optics_snapshot(d1_client):
    rows = query_rows(
        d1_client,
        """
        SELECT id, title, link, published_at, created_at, source_name, source_type, content
        FROM articles
        WHERE source_type = ?
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
            'generatedAt': datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%SZ'),
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

def process_feed_and_insert(feed, d1_client):
    """Fetch specific feed and insert directly to minimize memory usage"""
    # Note: d1_client instance sharing across threads? 
    # d1_client uses requests.post, which is thread-safe? Yes usually.
    # But let's instantiate local client if needed? Or just pass it.
    
    print(f"Processing {feed['title']}...")
    parsed = fetch_feed(feed['url'])
    if not parsed:
        print(f"Failed to fetch {feed['title']}")
        return 0
        
    count = 0
    for entry in parsed.entries:
        try:
            # Parse Date
            dt = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                dt = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                dt = datetime(*entry.updated_parsed[:6])
            
            # Generate ID (Hash of link)
            link = entry.link
            aid = hashlib.md5(link.encode('utf-8')).hexdigest()
            title = entry.title
            
            content, doi, authors = build_entry_content(entry)
            
            # Insert into D1 (Upsert logic: OR IGNORE)
            sql = """
            INSERT OR IGNORE INTO articles (id, title, link, published_at, source_name, source_type, content, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """
            
            params = [
                aid, 
                title, 
                link, 
                dt.strftime('%Y-%m-%d %H:%M:%S'), 
                feed['title'], 
                feed.get('type', 'journal'), 
                content[:16000], 
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            res = d1_client.query(sql, params)
            if res.get('success'):
                count += 1
            else:
                # print(f"Error inserting {title}: {res.get('error')}")
                pass
        except Exception as e:
            print(f"Error processing entry {title}: {e}")
            
    return count

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
        created_at TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_published ON articles(published_at);
    CREATE INDEX IF NOT EXISTS idx_created ON articles(created_at);
    CREATE INDEX IF NOT EXISTS idx_source_created ON articles(source_name, created_at);
    CREATE TABLE IF NOT EXISTS finance_tags (
        name TEXT PRIMARY KEY,
        url  TEXT,
        date TEXT
    );
    """
    d1.ensure_table(D1_TABLE, schema)
    
    # 3. Fetch Feeds (Parallel)
    feeds = get_feeds()
    print(f"Fetching {len(feeds)} feeds in parallel...")
    
    total_new = 0
    
    # Use ThreadPoolExecutor for I/O bound tasks
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        # Submit tasks
        future_to_feed = {executor.submit(process_feed_and_insert, feed, d1): feed for feed in feeds}
        
        for future in concurrent.futures.as_completed(future_to_feed):
            feed = future_to_feed[future]
            try:
                cnt = future.result()
                total_new += cnt
                if cnt > 0:
                    print(f"[{feed['title']}] Inserted {cnt} articles.")
            except Exception as exc:
                print(f"[{feed['title']}] Generated an exception: {exc}")

    print(f"Total articles inserted/checked: {total_new}")

    # 4. Cleanup Old Data (Retention: 7 days)
    print("Cleaning up old articles...")
    d1.query("DELETE FROM articles WHERE published_at < datetime('now', '-7 days')")

    # 5. Export optics snapshot (optional, but runs in the same hourly RSS task)
    print('Building optics snapshot...')
    snapshot = build_optics_snapshot(d1)
    kv_client = CloudflareKVClient()
    export_optics_snapshot(snapshot, kv_client)
    
    print("Done.")

if __name__ == "__main__":
    main()
