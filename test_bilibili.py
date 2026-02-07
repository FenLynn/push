import requests
import json

def test_bilibili():
    url = 'https://api.zxz.ee/api/hot/?type=bilibili'
    print(f"Testing {url}...")
    try:
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
        }
        res = requests.get(url, headers=headers, timeout=5)
        print(f"Status Code: {res.status_code}")
        if res.status_code == 200:
            data = res.json()
            if data.get('code') == 200:
                print("Success! Top 5 items:")
                for item in data['data'][:5]:
                    print(f"- {item.get('title')} ({item.get('hot')})")
            else:
                print(f"API Error: {data}")
        else:
            print("HTTP Error")
    except Exception as e:
        print(f"Exception: {e}")

if __name__ == "__main__":
    test_bilibili()
