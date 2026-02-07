import akshare as ak
import pandas as pd

print("--- Realtime Box Office ---")
try:
    df = ak.movie_boxoffice_realtime()
    print(df.head(2).to_string())
    print(df.columns)
except Exception as e:
    print(e)

print("\n--- Yearly Box Office ---")
try:
    import time
    df = ak.movie_boxoffice_yearly(time.strftime("%Y", time.localtime())) # Current year
    print(df.head(2).to_string())
    print(df.columns)
except Exception as e:
    print(e)

print("\n--- TV Hot ---")
try:
    df = ak.video_tv()
    print(df.head(2).to_string())
    print(df.columns)
except Exception as e:
    print(e)

print("\n--- Variety Show ---")
try:
    df = ak.video_variety_show()
    print(df.head(2).to_string())
    print(df.columns)
except Exception as e:
    print(e)
