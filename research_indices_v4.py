import akshare as ak
import pandas as pd
pd.set_option('display.max_rows', 100)
pd.set_option('display.unicode.east_asian_width', True)

print("Searching EM Boards...")
try:
    df = ak.stock_board_industry_name_em()
    mask = df['板块名称'].str.contains('平均|全A')
    if not df[mask].empty:
        print("Industry Matches:")
        print(df[mask])
    else:
        print("No matches in Industry.")
except Exception as e:
    print(f"Industry Error: {e}")

try:
    df = ak.stock_board_concept_name_em()
    mask = df['板块名称'].str.contains('平均|全A')
    if not df[mask].empty:
        print("Concept Matches:")
        print(df[mask])
    else:
        print("No matches in Concept.")
except Exception as e:
    print(f"Concept Error: {e}")
