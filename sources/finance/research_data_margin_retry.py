
import akshare as ak
import pandas as pd
import time

def retry_margin():
    print("\n--- Retry Margin Original Corrected ---")
    for i in range(5):
        try:
            print(f"Attempt {i+1}...")
            # No params
            df = ak.stock_margin_account_info(symbol="沪深两市")
            print("Success!")
            print(df.tail(2))
            return
        except Exception as e:
            print(f"Failed: {e}")
            try:
                # Try without symbol
                df = ak.stock_margin_account_info()
                print("Success (No Param)!")
                print(df.tail(2))
                return
            except Exception as e2:
                 print(f"Failed (No Param): {e2}")
            time.sleep(3)

if __name__ == "__main__":
    retry_margin()
