"""
Chengdu Real Estate Crawler (Lightweight Version)
成都房地产爬虫 - 轻量级版本，适合低配 VPS

Strategy:
1. Try requests-html first (uses pyppeteer, lighter than full Playwright)
2. Fallback to direct API if discovered
3. Last resort: simple HTTP + regex parsing

Data Source: https://blmp.cdzjryb.com/fplc_daas_portal/#/rybIndex
"""
import asyncio
import csv
import os
import re
import json
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.error
import ssl

# Output paths
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "estate_chengdu_history.csv"

# SSL context for HTTPS
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://blmp.cdzjryb.com/fplc_daas_portal/",
}

def try_api_direct():
    """
    Attempt to call the backend API directly.
    The Vue app likely calls an API endpoint for data.
    Common patterns:
    - /api/daily_trade
    - /fplc_daas_portal/api/...
    """
    # These are educated guesses based on common Vue+Spring patterns
    possible_apis = [
        "https://blmp.cdzjryb.com/fplc_daas_portal/api/getDailyTrade",
        "https://blmp.cdzjryb.com/fplc_daas_portal/api/rybIndex/data",
        "https://blmp.cdzjryb.com/api/fplc/daily",
    ]
    
    for api_url in possible_apis:
        try:
            req = urllib.request.Request(api_url, headers=HEADERS)
            with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
                data = response.read().decode('utf-8')
                # Check if it looks like JSON
                if data.startswith('{') or data.startswith('['):
                    print(f"[Chengdu] Found API: {api_url}")
                    return json.loads(data)
        except Exception as e:
            continue
    
    return None

def parse_from_static_html():
    """
    Fallback: Fetch the static HTML and try to extract any embedded data.
    Some Vue apps embed initial state in script tags.
    """
    url = "https://blmp.cdzjryb.com/fplc_daas_portal/"
    try:
        req = urllib.request.Request(url, headers=HEADERS)
        with urllib.request.urlopen(req, context=ctx, timeout=15) as response:
            html = response.read().decode('utf-8')
        
        # Look for embedded JSON data in script tags
        # Pattern: window.__INITIAL_STATE__ = {...}
        patterns = [
            r'window\.__INITIAL_STATE__\s*=\s*({.*?});',
            r'window\.APP_DATA\s*=\s*({.*?});',
            r'"dailyTrade"\s*:\s*({.*?})',
        ]
        
        for pattern in patterns:
            match = re.search(pattern, html, re.DOTALL)
            if match:
                try:
                    data = json.loads(match.group(1))
                    print(f"[Chengdu] Found embedded data")
                    return data
                except:
                    pass
        
        return None
    except Exception as e:
        print(f"[Chengdu] Static HTML parse failed: {e}")
        return None

def use_playwright_if_available():
    """
    Use Playwright only if available and system resources permit.
    Returns data or None.
    """
    try:
        from playwright.sync_api import sync_playwright
        
        print("[Chengdu] Using Playwright (may use ~200MB RAM)...")
        
        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-dev-shm-usage',  # Important for low-memory
                    '--disable-gpu',
                    '--single-process',  # Reduces memory
                    '--disable-extensions',
                ]
            )
            page = browser.new_page()
            page.goto("https://blmp.cdzjryb.com/fplc_daas_portal/#/rybIndex", wait_until="networkidle")
            
            # Wait for content
            page.wait_for_timeout(3000)
            
            # Click navigation
            page.click("text=信息公示")
            page.wait_for_timeout(1000)
            page.click("text=当日成交")
            page.wait_for_timeout(2000)
            
            # Extract table data
            data = []
            today = datetime.now().strftime("%Y-%m-%d")
            
            # Get all table rows
            rows = page.query_selector_all("table tr")
            for row in rows:
                cells = row.query_selector_all("td")
                if len(cells) >= 4:
                    try:
                        texts = [cell.inner_text().strip() for cell in cells]
                        if texts[0] in ['中心城区', '郊区新城', '全市']:
                            total_area = texts[1].replace(',', '') if texts[1] != '--' else '0'
                            units = texts[2].replace(',', '') if texts[2] != '--' else '0'
                            res_area = texts[3].replace(',', '') if texts[3] != '--' else '0'
                            
                            data.append({
                                'date': today,
                                'city': '成都',
                                'region': texts[0],
                                'total_area': float(total_area),
                                'resident_units': int(units),
                                'resident_area': float(res_area),
                            })
                    except:
                        pass
            
            browser.close()
            return data
            
    except ImportError:
        print("[Chengdu] Playwright not available, skipping browser method.")
        return None
    except Exception as e:
        print(f"[Chengdu] Playwright failed: {e}")
        return None

def save_to_csv(data: list):
    """Append data to history CSV."""
    if not data:
        print("[Chengdu] No data to save.")
        return
    
    file_exists = HISTORY_FILE.exists()
    
    with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["date", "city", "region", "total_area", "resident_units", "resident_area"])
        if not file_exists:
            writer.writeheader()
        writer.writerows(data)
    
    print(f"[Chengdu] Saved {len(data)} records to {HISTORY_FILE}")

def main():
    print("=" * 50)
    print("Chengdu Real Estate Crawler (Lightweight)")
    print("=" * 50)
    
    data = None
    
    # Strategy 1: Try direct API
    print("[Chengdu] Strategy 1: Trying direct API...")
    api_data = try_api_direct()
    if api_data:
        # Parse API response (structure depends on actual API)
        # This is a placeholder - adjust based on real response
        print(f"[Chengdu] API data: {api_data}")
        # TODO: Parse api_data into our format
    
    # Strategy 2: Try embedded data in HTML
    if not data:
        print("[Chengdu] Strategy 2: Trying embedded HTML data...")
        embedded = parse_from_static_html()
        if embedded:
            print(f"[Chengdu] Embedded data: {embedded}")
    
    # Strategy 3: Use Playwright if available
    if not data:
        print("[Chengdu] Strategy 3: Trying Playwright...")
        data = use_playwright_if_available()
    
    # Results
    if data:
        print("\n[Chengdu] Extracted Data:")
        for row in data:
            print(f"  {row['region']}: 总面积={row['total_area']}㎡, 住宅套数={row['resident_units']}套")
        save_to_csv(data)
    else:
        print("[Chengdu] All strategies failed. Manual intervention required.")

if __name__ == "__main__":
    main()
