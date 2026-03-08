import os
import sys
import asyncio
import json
from datetime import datetime
import hashlib
import concurrent.futures

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
    print("Missing dependencies. Please run: pip install feedparser requests python-dotenv")
    sys.exit(1)

# Configuration from env or default
D1_TABLE = "articles"

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
            
            content = ""
            if hasattr(entry, 'summary'): content = entry.summary
            if hasattr(entry, 'content'): content = entry.content[0].value
            
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
                content[:5000], 
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
    
    print("Done.")

if __name__ == "__main__":
    main()
