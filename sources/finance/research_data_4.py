
import akshare as ak
import pandas as pd

def check_bond():
    print("\n--- Bond Data ---")
    try:
        df = ak.bond_zh_us_rate()
        print(df.columns)
        print(df.tail(2))
    except Exception as e:
        print(e)

def check_margin_index():
    print("\n--- Margin & Index ---")
    try:
        # Check if we can get Total Market Turnover or just use SSE Index Volume
        # Margin data
        df_margin = ak.stock_margin_account_info()
        print("Margin Cols:", df_margin.columns)
        
        # SSE Index
        df_index = ak.index_zh_a_hist(symbol="000001", period="daily")
        print("Index Cols:", df_index.columns)
    except Exception as e:
        print(e)

if __name__ == "__main__":
    check_bond()
    check_margin_index()
