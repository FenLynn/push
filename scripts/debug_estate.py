import requests
from bs4 import BeautifulSoup
import urllib3

urllib3.disable_warnings()

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
}

def test_chengdu():
    print("--- Testing Chengdu ---")
    url = "https://www.cdzjryb.com/SCXX/Default.aspx?action=ucEveryday2"
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        res.encoding = 'utf-8'
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            soup = BeautifulSoup(res.text, 'html.parser')
            # Try to find data tables
            tables = soup.find_all('table')
            print(f"Found {len(tables)} tables")
            for i, table in enumerate(tables):
                print(f"Table {i}: {table.get_text()[:100].strip()}...")
                
            # Check for specific keywords
            if "商品房" in res.text:
                print("Keyword '商品房' found.")
            if "二手房" in res.text:
                print("Keyword '二手房' found.")
    except Exception as e:
        print(f"Error: {e}")

def test_xian():
    print("\n--- Testing Xi'an ---")
    url = "http://zfyxdj.xa.gov.cn/zfrgdjpt/index.html"
    # Note: Xi'an might be harder
    try:
        res = requests.get(url, headers=headers, verify=False, timeout=10)
        res.encoding = 'utf-8'
        print(f"Status: {res.status_code}")
        if res.status_code == 200:
            print(f"Title: {res.text[:200]}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test_chengdu()
    # test_xian()
