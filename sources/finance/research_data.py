
import akshare as ak
import pandas as pd
from datetime import datetime

def check_margin():
    print("\n--- Margin Balance ---")
    try:
        # 融资融券余额 (General Detail)
        # ak.stock_margin_account_info() usually returns total market margin
        df = ak.stock_margin_account_info()
        print(df.tail())
        print("Margin Data Found")
    except Exception as e:
        print(f"Margin Error: {e}")

def check_forex():
    print("\n--- Forex ---")
    try:
        # USD/CNY, EUR/CNY etc.
        # ak.currency_boc_safe() gives spot rates from BOC
        # But maybe we want historical data for plotting?
        # ak.currency_hist_sina(symbol="USDCNY")?
        # Let's try currency_boc_safe for current
        # For history: ak.fx_spot_quote_recent(symbol='USDCNY') -> might be too short
        # ak.currency_pair_map("USDCNY") -> ?
        pass
    except: pass
    
    # Let's try simple f x rates
    try:
        # Spot rates
        df = ak.fx_spot_quote_recent(symbol='USDCNY') 
        print(f"USDCNY: {len(df)} rows")
    except Exception as e:
        print(f"Forex Error: {e}")

def check_commodities():
    print("\n--- Commodities ---")
    try:
        # CRB Index?
        # Or specific futures?
        # ak.futures_foreign_hist(symbol="CRB")? 
        # Often easier to get specific contracts like Gold/Oil
        pass
    except: pass

def check_indices():
    print("\n--- Global Indices (SOX) ---")
    try:
        # SOX
        df = ak.index_us_stock_sina(symbol=".SOX")
        print(df.tail())
    except Exception as e:
        print(f"SOX Error: {e}")

def check_shibor():
    print("\n--- Shibor ---")
    try:
        df = ak.rate_interbank(market="Shanghai Interbank Offered Rate", symbol="Shibor")
        print(df.tail())
    except Exception as e:
        print(f"Shibor Error: {e}")

def check_bonds():
    print("\n--- Bond Yields ---")
    try:
        # US vs CN 10Y
        df = ak.bond_zh_us_rate()
        print(df.tail())
    except Exception as e:
        print(f"Bond Error: {e}")

if __name__ == "__main__":
    check_margin()
    check_indices() # SOX
    check_shibor()
    check_bonds()
    # Forex and Commodities need more specific search
