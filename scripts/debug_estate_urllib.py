import urllib.request
import urllib.error
import urllib.parse
import re
import ssl
import json

# Ignore SSL errors
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

common_headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
}

def get_html(url, referer=None, encoding='utf-8'):
    try:
        headers = common_headers.copy()
        if referer:
            # simple trick: ensure referer is ascii safe if needed, or just let python handle if it can
            # but standard http requires ascii headers.
            headers["Referer"] = urllib.parse.quote(referer, safe=':/')
            
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, context=ctx, timeout=10) as response:
            data = response.read()
            return data.decode(encoding, errors='ignore')
    except Exception as e:
        print(f"Failed to fetch {url}: {e}")
        return None

def test_chengdu_api():
    print("--- Testing Chengdu API (urllib) ---")
    url = "https://www.cdzjryb.com/Service/GetDailyTrade.ashx"
    # Use the referer that likely makes this request allowed
    # The page "https://www.cdzjryb.com/SCXX/Default.aspx?action=ucEveryday2" is where the user sees it.
    # But often the referer matching the page URL works.
    referer = "https://www.cdzjryb.com/SCXX/Default.aspx?action=ucEveryday2"
    html = get_html(url, referer=referer)
    if html:
        print(f"API Fetched {len(html)} bytes.")
        print(f"API Snippet: {html[:500]}")
    else:
        print("API Fetch failed.")

def test_xian():
    print("\n--- Testing Xi'an (urllib) ---")
    url = "https://zfyxdj.xa.gov.cn/zfrgdjpt/index.html"
    print(f"Fetching {url}...")
    html = get_html(url)
    if not html:
        print("Xi'an fetch returned None")
        return
        
    print(f"Fetched {len(html)} bytes.")
    print(f"Title snippet: {html[:200]}")

if __name__ == "__main__":
    test_chengdu_api()
    test_xian()
