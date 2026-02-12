import os
import sys
from dotenv import load_dotenv
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.d1_client import D1Client

load_dotenv()
d1 = D1Client()
# Add a few hours buffer to "now" just in case of TZ
sql = "SELECT id, title, published_at, source_name FROM articles WHERE published_at > '2026-02-14 00:00:00' ORDER BY published_at DESC LIMIT 5"
res = d1.query(sql)

if res.get('success'):
    print("Future Articles Found:")
    rows = res['data'][0]['results'] if 'results' in res['data'][0] else res['data'][0]
    for row in rows:
        print(f"[{row['source_name']}] {row['published_at']} | {row['title']}")
else:
    print(f"Query Failed: {res.get('error')}")
