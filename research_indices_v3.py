import akshare as ak
import pandas as pd

pd.set_option('display.max_rows', 100)
pd.set_option('display.unicode.east_asian_width', True)

print("--- EM Indices Search (General) ---")
try:
    # ak.stock_zh_index_spot_em usually returns main indices
    df = ak.stock_zh_index_spot_em(symbol="全部") 
    if df is not None:
         # Filter
         mask = df['名称'].str.contains('全A|平均|等权|中证A|全指', na=False)
         print(df[mask][['代码', '名称', '最新价', '涨跌幅']])
except Exception as e:
    print(f"EM Error: {e}")

print("\n--- Sina Search ---")
try:
    df = ak.stock_zh_index_spot_sina()
    mask = df['名称'].str.contains('全A|平均|等权|全指', na=False)
    print(df[mask][['代码', '名称', '最新价']])
except Exception as e:
    print(f"Sina Error: {e}")
