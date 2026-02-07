import akshare as ak
try:
    print("Testing THS All-A...")
    # THS Concepts often have '88xxxx'
    # Try board_industry?
    # ak.stock_board_concept_name_ths() ?
    # But user wants "Index".
    # Try Sina for '399001' (Deep Component) and '000002' (A Share)
    df = ak.stock_zh_index_spot_sina()
    print(df[df['代码'].isin(['sh000002', 'sz399001', 'sh000001'])])

    print("\nTesting HK Index (Sina)...")
    # There is no direct stock_hk_index_spot_sina in common usage
    # Maybe try global index?
    # ak.index_global_sina ?
    # ak.stock_hk_daily(symbol="02800") (Tracker Fund)?
    
except Exception as e:
    print(e)
