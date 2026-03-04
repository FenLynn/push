import sys
import os
import requests
import feedparser
import time
from datetime import datetime
import json
import configparser

# Setup paths (Assuming running from project root or scripts dir)
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(ROOT_DIR)

# Manually load config since 'core.config' might have import issues in isolated script
CONFIG_PATH = os.path.join(ROOT_DIR, 'config', 'default.ini')

def load_journals():
    # Use BasicInterpolation or None to avoid errors with ${VAR} syntax in default.ini
    config = configparser.ConfigParser(interpolation=None)
    config.optionxform = str # Preserve case like core/config.py
    read_files = config.read(CONFIG_PATH, encoding='utf-8')
    print(f"Read config from: {read_files}")
    print(f"Sections found: {config.sections()}")
    
    if 'paper.journals' in config:
        j = dict(config['paper.journals'])
        print(f"Loaded {len(j)} journals. Keys sample: {list(j.keys())[:5]}")
        return j
    else:
        print("Warning: Section [paper.journals] not found!")
        
    return {}

def test_feed(title, url):
    print(f"Testing {title}...")
    print(f"URL: {url}")
    
    try:
        start_time = time.time()
        resp = requests.get(url, timeout=30, headers={
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        })
        duration = time.time() - start_time
        
        if resp.status_code != 200:
            print(f"❌ HTTP Error: {resp.status_code}")
            return
            
        print(f"✅ HTTP 200 (Time: {duration:.2f}s, Size: {len(resp.content)} bytes)")
        
        feed = feedparser.parse(resp.content)
        if feed.bozo:
            print(f"⚠️ Feedparser Bozo: {feed.bozo_exception}")
            
        if not feed.entries:
            print("❌ No entries found!")
            return
            
        print(f"✅ Found {len(feed.entries)} entries.")
        if feed.entries:
            first_entry = feed.entries[0]
            print(f"   Sample Title: {first_entry.title}")
            
            # Check dates
            dt = None
            if hasattr(first_entry, 'published_parsed') and first_entry.published_parsed:
                dt = datetime(*first_entry.published_parsed[:6])
                print(f"   Published: {dt}")
            elif hasattr(first_entry, 'updated_parsed') and first_entry.updated_parsed:
                dt = datetime(*first_entry.updated_parsed[:6])
                print(f"   Updated: {dt}")
            else:
                print("   ⚠️ No date info found")
                
            if dt:
                age = datetime.now() - dt
                print(f"   Age: {age}")
                
    except Exception as e:
        print(f"❌ Exception: {e}")

def main():
    print("=== Paper RSS Debug Tool ===")
    
    journals = load_journals()
    if not journals:
        print("Error: No journals found in config!")
        # Fallback manual list
        journals = {
            'Nature': 'https://www.nature.com/nature.rss',
            'Optics Express': 'https://opg.optica.org/rss/opex_feed.xml',
            'Optics Letters': 'https://opg.optica.org/rss/ol_feed.xml'
        }

    # Select targets
    targets = [
        'Nature', 
        'Nature Communications',
        'Optics Express', 
        'Optics Letters',
        'Applied Optics',
        'Photonics Research',
        'IEEE Journal of Quantum Electronics'
    ]
    
    for name in targets:
        url = journals.get(name)
        if not url:
            print(f"\nSkipping {name} (Not in config)")
            continue
            
        print("-" * 50)
        test_feed(name, url)
        
    print("\n=== Done ===")

if __name__ == "__main__":
    main()
