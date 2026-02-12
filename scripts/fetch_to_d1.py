import os
import sys
import asyncio
import json
from datetime import datetime
import hashlib

# Add project root to sys.path to import core modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    import feedparser
    import requests
    from core.d1_client import D1Client
    from dotenv import load_dotenv
    
    # Load .env explicitly for local run
    load_dotenv(os.path.join(os.path.dirname(os.path.dirname(__file__)), '.env'))
except ImportError:
    print("Missing dependencies. Please run: pip install feedparser requests")
    sys.exit(1)

# Configuration from env or default
D1_TABLE = "articles"

def get_feeds():
    """
    Get feeds list. 
    Ideally this comes from a shared config (feeds.json) or parsed from default.ini.
    For this script, we will load from 'feeds.json' which should be committed to the repo.
    """
    feeds_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config', 'feeds.json')
    if not os.path.exists(feeds_path):
        # Fallback: try to parse default.ini if feeds.json missing? 
        # For Cloud Native, explicit feeds.json is better.
        print(f"Error: {feeds_path} not found.")
        return []
    
    with open(feeds_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def fetch_feed(feed_url, max_retries=3):
    """Fetch a single feed with retries"""
    for attempt in range(max_retries):
        try:
            resp = requests.get(feed_url, timeout=30, headers={
                'User-Agent': 'Mozilla/5.0 (GitHub Actions; Cloud Native Fetcher)'
            })
            if resp.status_code == 200:
                return feedparser.parse(resp.content)
        except Exception as e:
            print(f"Error fetching {feed_url}: {e}")
            if attempt < max_retries - 1:
                import time
                time.sleep(2)
    return None

def main():
    # 1. Initialize D1
    d1 = D1Client()
    if not d1.enabled:
        print("D1 Client not enabled. Check CLOUDFLARE_D1_* env vars.")
        sys.exit(1)

    # 2. Ensure Table Exists
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
    """
    d1.ensure_table(D1_TABLE, schema)
    
    # 3. Fetch Feeds
    feeds = get_feeds()
    print(f"Fetching {len(feeds)} feeds...")
    
    new_count = 0
    total_articles = 0
    
    for feed in feeds:
        print(f"Processing {feed['title']}...")
        parsed = fetch_feed(feed['url'])
        if not parsed:
            print(f"Failed to fetch {feed['title']}")
            continue
            
        for entry in parsed.entries:
            # Parse Date
            dt = datetime.now()
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                dt = datetime(*entry.published_parsed[:6])
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                dt = datetime(*entry.updated_parsed[:6])
            
            # Generate ID (Hash of link)
            link = entry.link
            aid = hashlib.md5(link.encode('utf-8')).hexdigest()
            
            # Prepare Data
            title = entry.title
            content = ""
            if hasattr(entry, 'summary'): content = entry.summary
            if hasattr(entry, 'content'): content = entry.content[0].value
            
            # Insert into D1 (Upsert logic: OR IGNORE)
            # D1 doesn't support "INSERT OR IGNORE" in standard SQLite via HTTP API sometimes? 
            # Actually standard SQLite supports it. Let's try.
            
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
                content[:5000],  # Truncate content to save D1 space usage? Or maybe full? 
                                # D1 limits: 100MB total for free. 5000 chars is safe.
                datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            ]
            
            res = d1.query(sql, params)
            if res.get('success'):
                # Check if it was actually inserted? D1 API doesn't always return rows affected easily in 'meta'.
                pass
            else:
                print(f"Error inserting {title}: {res.get('error')}")

    # 4. Cleanup Old Data (Retention: 7 days)
    print("Cleaning up old articles...")
    d1.query("DELETE FROM articles WHERE published_at < datetime('now', '-7 days')")
    
    print("Done.")

if __name__ == "__main__":
    main()
