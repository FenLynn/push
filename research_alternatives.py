import requests
# import yfinance as yf

print("--- Testing Tencent (gtimg) ---")
try:
    # sh000001 (ShangZheng), hkHSI (HangSeng), sh510300 (ETF)
    url = "http://qt.gtimg.cn/q=s_sh000001,s_hkHSI,sh510300" 
    # s_ prefix for simple simplified data, regular for full
    # hkHSI might need rt_hkHSI?
    # Let's try standard codes
    url = "http://qt.gtimg.cn/q=sh000001,hkHSI,sh588090"
    r = requests.get(url, timeout=5)
    print(r.text)
except Exception as e:
    print(f"Tencent Error: {e}")

# print("\n--- Testing Yahoo (yfinance) ---")
# try:
#     hsi = yf.Ticker("^HSI")
#     hist = hsi.history(period="1d")
#     if not hist.empty:
#         print(f"HSI Last: {hist.iloc[-1]['Close']:.2f}")
#     else:
#         print("HSI Empty")
# except Exception as e:
#     print(f"Yahoo Error: {e}")
