from .config import *
from .net import *
from .time import *

def get_us_info():
    _date = ak.stock_us_hist_min_em(start_date='2025-01-01 09:32:00',symbol="107.SPY").iloc[-1]['时间']
    us_dict={'107.SPY':['标普500ETF'],'105.QQQ':['纳斯达克100ETF'],'105.TSLA':['特斯拉'],'105.AAPL':['苹果'],'105.MSFT':['微软'],'105.NVDA':['英伟达'],'106.BABA':['阿里巴巴']}
    all_us_day_info=ak.stock_us_spot_em()
    all_us_day_info=all_us_day_info[all_us_day_info['代码'].isin(list(us_dict.keys()))]
    all_us_day_info['成交额']=all_us_day_info['成交额'].map(lambda x: x/100000000.)
    all_us_day_info=all_us_day_info.loc[:,('名称','涨跌幅','市盈率','成交额','代码')]
    all_us_day_info=all_us_day_info.reset_index(drop=True)
    all_us_day_info.loc[(all_us_day_info['代码']=='107.SPY'), '名称'] = '标普500'
    all_us_day_info.loc[(all_us_day_info['代码']=='105.QQQ'), '名称'] = '纳斯达克100'
    all_us_day_info.index = all_us_day_info.index+1
    return _date,all_us_day_info
    
def get_index():    
    def gen_match_dc(df,_list,match_replace):
        for i in _list:
            match_replace[i]=df.loc[(df['代码']==i), '涨跌幅'].iloc[0]
            pass
        return match_replace
    
    a50=get_A50()
    match_replace={'A50':a50['pct']}
    rpl_list=['N225','DJIA','NDX','SPX','GDAXI','FTSE','FCHI']    
    df=get_global_index()    
    return gen_match_dc(df,rpl_list,match_replace)

def get_A50():
    info={}
    url = "http://futsseapi.eastmoney.com/static/104_CN00Y_qt"
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
    }
    r = requests.get(url,headers=headers)
    data_json = r.json()
    if not data_json["qt"]["mcj"]:
        return None
    #print (data_json.text)
    info['close']=data_json["qt"]["p"]
    info['pct']=data_json["qt"]["zdf"]
    info['name']=data_json["qt"]["name"]
    info['code']=data_json["qt"]["dm"]
    return info

def get_global_index():
    url = "https://45.push2.eastmoney.com/api/qt/ulist.np/get?fid=f3&pi=0&pz=40&po=1&fields=f14,f12,f13,f2,f3,f4,f6,f104,f105,f106&np=1&secids=100.TOP40%2C100.AS51%2C100.ATX%2C100.BFX%2C100.BVSP%2C100.TSX%2C100.PX%2C100.FCHI%2C100.HEX%2C100.GDAXI%2C100.AEX%2C100.ASE%2C100.SENSEX%2C100.ICEXI%2C100.JKSE%2C100.N225%2C100.KS11%2C100.ISEQ%2C100.MIB%2C100.KLSE%2C100.MXX%2C100.NZ50%2C100.KSE100%2C100.WIG%2C100.RTS%2C100.OMXSPI%2C100.STI%2C100.CSEALL%2C100.IBEX%2C100.SSMI%2C100.SET%2C100.TWII%2C100.FTSE%2C100.DJIA%2C100.NDX%2C100.SPX%2C100.VNINDEX&_=1671170786877"
    headers = {
        'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8',
        'user-agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/68.0.3440.106 Safari/537.36',
    }
    r = requests.get(url,headers=headers)
    data_json = r.json()
    temp_df = pd.DataFrame(data_json["data"]["diff"])
    temp_df.columns = [
            "最新价",
            "涨跌幅",
            "涨跌额",
            "-",
            "代码",
            "-",
            "名称",
            "-",
            "-",
            "-",
        ]
    temp_df = temp_df[
        [
        "名称",
        "代码",
        "最新价",
        "涨跌幅",                
        ]
    ]
    temp_df['涨跌幅']=temp_df['涨跌幅']*0.01
    temp_df['最新价']=temp_df['最新价']*0.01
    temp_df=temp_df.sort_values(by='涨跌幅',ascending=False)  
    temp_df=temp_df.reset_index(drop=True)
    temp_df.index=temp_df.index+1
    return temp_df

def get_gold_price():        
    request_url='https://api.lolimi.cn/API/huangj/api.php'
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    price={}
    try:
        response = safe_request(request_url, headers=headers)
        data=response.json()
        mylog.debug(f'Info: gold price: {data}')
        if data['code'] == 200:
            price['金店']={}
            price['国际']={}
            price['国内']={}
            for i in data['国内十大金店']:
                if i['品牌'] in ['内地周大福','内地周生生','内地六福珠宝','老凤祥','中国黄金']:
                    price['金店'][i['品牌']]=i['黄金价格']
            for i in data['国际黄金']:
                if i['品种'] in ['国际金价','国际银价']:
                    price['国际'][i['品种']]=i['最新价']
            for i in data['国内黄金']:
                if i['品种'] in ['国内金价','投资金条','黄金回收价格']:
                    price['国内'][i['品种']]=i['最新价']
            return price
        else:
            return price
    except:
        print ('error')
        return price