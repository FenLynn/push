
import akshare as ak
import pandas as pd
from datetime import datetime

def check_shibor_final():
    print("\n--- Shibor (Final Test) ---")
    try:
        # Explicit params based on source code reading
        # market="上海银行同业拆借市场"
        # symbol="Shibor人民币"
        # indicator="隔夜", "1周", "3月", "1年"
        
        df = ak.rate_interbank(market="上海银行同业拆借市场", symbol="Shibor人民币", indicator="隔夜")
        print("Shibor O/N Success")
        print(df.tail())
        
        df = ak.rate_interbank(market="上海银行同业拆借市场", symbol="Shibor人民币", indicator="3月")
        print("Shibor 3M Success")
        print(df.tail())
    except Exception as e:
        print(f"Shibor Final Failed: {e}")

def check_forex_boc():
    print("\n--- Forex (BOC SAFE) ---")
    try:
        df = ak.currency_boc_safe()
        print("BOC Safe Success")
        print(df.tail())
    except Exception as e:
        print(f"BOC Safe Failed: {e}")

def check_commodities_gold():
    print("\n--- Commodities (Gold) ---")
    try:
        # COMEX Gold
        df = ak.futures_foreign_hist(symbol="GC") 
        print("Gold Hist Success")
        print(df.tail())
    except Exception as e:
        print(f"Gold Hist Failed: {e}")

if __name__ == "__main__":
    check_shibor_final()
    check_forex_boc()
    check_commodities_gold()
