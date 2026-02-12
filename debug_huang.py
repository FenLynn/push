import feedparser
from datetime import datetime, timedelta
import sys

# Huang Liangjin's RSS
url = 'https://rsshub.pseudoyu.com/orcid/0000-0001-9119-0345'
print(f'Checking {url}...')
d = feedparser.parse(url)
print(f'Feed Title: {d.feed.get("title", "Unknown")}')
print(f'Entries: {len(d.entries)}')

now = datetime.now()
count_25h = 0

for i, e in enumerate(d.entries):
    dt = None
    if hasattr(e, 'published_parsed') and e.published_parsed:
        dt = datetime(*e.published_parsed[:6])
    elif hasattr(e, 'updated_parsed') and e.updated_parsed:
        dt = datetime(*e.updated_parsed[:6])
    
    title = e.title
    
    if dt:
        diff = now - dt
        is_recent = diff < timedelta(hours=25)
        if is_recent:
            count_25h += 1
            print(f'[{i}] [RECENT] {title[:40]}... | {dt} | Age: {diff.total_seconds()/3600:.1f}h')
        else:
            if i < 5: # Print first few non-recent to check
                print(f'[{i}] [OLD] {title[:40]}... | {dt} | Age: {diff.total_seconds()/3600:.1f}h')
    else:
        print(f'[{i}] [NO DATE] {title[:40]}... | No date found')

print(f"Total articles within last 25h: {count_25h}")
