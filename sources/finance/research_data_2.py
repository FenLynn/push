
import akshare as ak
import pandas as pd
from datetime import datetime

def check_margin_retry():
    print("\n--- Margin Balance (Retry) ---")
    try:
        # Retry logic handled by akshare? No.
        # Just try again.
        df = ak.stock_margin_account_info()
        print(df.tail())
        print("Success!")
    except Exception as e:
        print(f"Margin Retry Failed: {e}")

def check_shibor_fix():
    print("\n--- Shibor (Fix) ---")
    try:
        # Try without market param, or with correct symbol
        # Old API: ak.rate_interbank(market="...")
        # New API might differ.
        # Let's try likely variations
        try:
            df = ak.rate_interbank(symbol="Shibor")
            print("Method 1 (symbol='Shibor'): Success")
            print(df.tail())
            return
        except: pass
        
        try:
            df = ak.rate_interbank(market="Shibor")
            print("Method 2 (market='Shibor'): Success")
            print(df.tail())
            return
        except: pass

    except Exception as e:
        print(f"Shibor Fix Failed: {e}")

def check_commodities():
    print("\n--- Commodities ---")
    try:
        # COMEX Gold as proxy? 
        # Or CRB Index?
        # ak.index_commodity_sina(symbol="...")
        # symbols: "CRB" ?
        # Let's try futures_foreign_hist for "COMEX黄金" 
        # Symbol might be "GC"
        df = ak.futures_foreign_hist(symbol="CRB") 
        print("CRB Index Found")
        print(df.tail())
    except Exception as e:
        print(f"CRB Error: {e}")
        try:
            # Try Gold
            df = ak.futures_foreign_hist(symbol="GC")
            print("Gold Found")
            print(df.tail())
        except: pass

def check_forex_hist():
    print("\n--- Forex History ---")
    try:
        # USDCNY
        # ak.currency_hist_sina(symbol="USDCNY") 
        # Check docs or try common symbols
        df = ak.currency_hist_sina(symbol="USDCNY")
        print("USDCNY Hist Found")
        print(df.tail())
    except Exception as e:
        print(f"Forex Hist Error: {e}")

if __name__ == "__main__":
    check_margin_retry()
    check_shibor_fix()
    check_commodities()
    check_forex_hist()
