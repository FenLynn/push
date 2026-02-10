"""
Xi'an Real Estate Crawler (Playwright-based)
西安房地产爬虫 - 使用 Playwright 渲染动态页面

Data Source: https://zfyxdj.xa.gov.cn/zfrgdjpt/index.html
Requires: playwright (will be installed in Docker)
"""
import asyncio
import csv
import os
from datetime import datetime
from pathlib import Path

try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Playwright not installed. Run in Docker or: pip install playwright && playwright install chromium")
    exit(1)

# Output paths
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)
HISTORY_FILE = DATA_DIR / "estate_xian_history.csv"

async def scrape_xian():
    """Scrape Xi'an daily real estate transaction data."""
    url = "https://zfyxdj.xa.gov.cn/zfrgdjpt/index.html"
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"[Xi'an] Navigating to {url}...")
        await page.goto(url, wait_until="networkidle", timeout=30000)
        await page.wait_for_timeout(3000)
        
        # Extract data - Xi'an structure may differ
        print("[Xi'an] Extracting data...")
        
        # Try to find transaction numbers
        content = await page.content()
        
        data = []
        today = datetime.now().strftime("%Y-%m-%d")
        
        # Xi'an page structure is different - we'll parse what we can
        # Look for common patterns in the HTML
        # This is a placeholder - actual parsing depends on site structure
        
        # Fallback: just record that we attempted
        data.append({
            "date": today,
            "city": "西安",
            "region": "全市",
            "total_area": 0,
            "resident_units": 0,
            "resident_area": 0,
            "note": "需要进一步分析页面结构"
        })
        
        await browser.close()
        return data

def save_to_csv(data: list):
    """Append data to history CSV."""
    if not data:
        print("[Xi'an] No data to save.")
        return
    
    file_exists = HISTORY_FILE.exists()
    
    with open(HISTORY_FILE, "a", newline="", encoding="utf-8") as f:
        fieldnames = ["date", "city", "region", "total_area", "resident_units", "resident_area", "note"]
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        if not file_exists:
            writer.writeheader()
        writer.writerows(data)
    
    print(f"[Xi'an] Saved {len(data)} records to {HISTORY_FILE}")

async def main():
    print("=" * 50)
    print("Xi'an Real Estate Crawler")
    print("=" * 50)
    
    data = await scrape_xian()
    
    if data:
        print("\n[Xi'an] Extracted Data:")
        for row in data:
            print(f"  {row['region']}: 总面积={row['total_area']}㎡, 住宅套数={row['resident_units']}套")
        
        save_to_csv(data)
    else:
        print("[Xi'an] Failed to extract data.")

if __name__ == "__main__":
    asyncio.run(main())
