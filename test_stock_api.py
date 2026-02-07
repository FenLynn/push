import akshare as ak
import os
import requests
import time

# 候选代理
PROXIES = [
    "http://192.168.12.21:7890",
    "http://127.0.0.1:7890",
    ""
]

def test_proxy(proxy):
    print(f"\nTesting proxy: {proxy}")
    if proxy:
        os.environ["http_proxy"] = proxy
        os.environ["https_proxy"] = proxy
    else:
        os.environ.pop("http_proxy", None)
        os.environ.pop("https_proxy", None)
        
    try:
        start = time.time()
        # 测试百度
        requests.get("https://www.baidu.com", timeout=3)
        print(f"  [OK] Baidu ({time.time() - start:.2f}s)")
    except Exception as e:
        print(f"  [FAIL] Baidu: {e}")

    try:
        start = time.time()
        # 测试东财接口 (EM)
        df = ak.stock_zh_a_spot_em()
        print(f"  [OK] EM API: Got {len(df)} rows ({time.time() - start:.2f}s)")
    except Exception as e:
        print(f"  [FAIL] EM API: {e}")

# 测试不同的接口
def test_apis():
    print("\nTesting Alternative APIs (without proxy)...")
    os.environ.pop("http_proxy", None)
    os.environ.pop("https_proxy", None)
    
    apis = [
        ("EM", ak.stock_zh_a_spot_em),
        ("Sina", ak.stock_zh_a_spot),
        # ("THS-NewHigh", lambda: ak.stock_rank_cxg_ths(symbol="历史新高")), # 已知可用
    ]
    
    for name, func in apis:
        try:
            start = time.time()
            df = func()
            print(f"  [OK] {name}: {len(df)} rows ({time.time() - start:.2f}s)")
            print(f"       Columns: {df.columns.tolist()[:5]}...")
        except Exception as e:
            print(f"  [FAIL] {name}: {e}")

if __name__ == "__main__":
    test_apis()
