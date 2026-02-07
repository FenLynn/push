
import akshare as ak
import pandas as pd
import time

def check_alternatives():
    print("\n--- Margin Alternatives ---")
    try:
        print("Fetching SSE Margin...")
        df_sh = ak.stock_margin_sse(start_date="20240101")
        print("SSE Cols:", df_sh.columns)
        print(df_sh.tail(2))
        
        time.sleep(1)
        
        print("Fetching SZSE Margin...")
        df_sz = ak.stock_margin_szse(date="20240101") # SZSE might need specific date or range?
        # ak.stock_margin_szse(date="20240206") usually returns one day?
        # Let's check ak.stock_margin_szse() doc or behavior. 
        # Actually ak.stock_margin_detail_szse? Can we get history?
        # ak.stock_margin_szse implies history?
        # Let's try stock_margin_account_info again with verify=False?
    except Exception as e:
        print(f"Alt Failed: {e}")

if __name__ == "__main__":
    check_alternatives()
