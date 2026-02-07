import akshare as ak
import pandas as pd

pd.set_option('display.max_rows', 100)
pd.set_option('display.unicode.east_asian_width', True)

print("--- Sina Indices ---")
try:
    df = ak.stock_zh_index_spot_sina()
    # Search for relevant keywords
    matches = df[df['名称'].str.contains('A|全|恒生|同花顺', na=False)]
    print(matches[['代码', '名称', '最新价']])
except Exception as e:
    print(f"Sina Error: {e}")

print("\n--- HK Indices (EM) ---")
try:
    df = ak.stock_hk_index_spot_em()
    matches = df[df['名称'].str.contains('恒生', na=False)]
    print(matches[['代码', '名称', '最新价']])
except Exception as e:
    print(f"HK Error: {e}")
