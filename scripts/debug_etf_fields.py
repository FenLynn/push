
import requests

def test_tencent_source():
    code = "sh510300"
    url = f"http://qt.gtimg.cn/q={code}"
    print(f"Fetching {url}...")
    resp = requests.get(url)
    content = resp.text
    print(f"Raw Content: {content}")
    
    parts = content.split('~')
    for i, p in enumerate(parts):
        print(f"[{i}] {p}")

if __name__ == "__main__":
    test_tencent_source()
