import sys
import sys
sys.path.append("..")
from cloud import *
from cloud.utils.lib import *

if is_use_proxy:
    use_proxy()
df_all=ak.stock_zh_a_spot_em()


def format_stock_data(_df):
    df=_df        
    for i in ['代码','名称','最新价','涨跌幅','成交额','振幅','换手率','市盈率-动态','市净率','总市值','流通市值','60日涨跌幅','年初至今涨跌幅']:
        #if i== '总市值' or i== '流通市值' or i== '成交额' :
        if i== '总市值' or i== '流通市值':
            df[i]=round(df[i]/100000000.,2)
        df[i]=round(df[i],2)
    df.rename(columns={'换手率':'换手','市盈率-动态':'PE(动)','市净率':'PB','60日涨跌幅':'60日涨幅','年初至今涨跌幅':'年初至今涨幅'},inplace=True)
    df.sort_values(by="涨跌幅",ascending=False)
    df=df.reset_index(drop=True)
    df.index=df.index+1

def get_diy_stock_data(stock):
    df=df_all.loc[:,['代码','名称','最新价','涨跌幅','成交额','振幅','换手率','市盈率-动态','市净率','总市值','流通市值','60日涨跌幅','年初至今涨跌幅']]
    df = df[df.名称.isin(stock)]
    format_stock_data(df)
    df = df.reset_index(drop=True)
    df=df.loc[:,('名称','涨跌幅','换手','代码','成交额','最新价')]
    df['market']='cn'
    df.rename(columns={'名称':'name','涨跌幅':'growth_rate','代码':'code','成交额':'turnover','换手':'change','最新价':'close'},inplace=True)
    result = df.to_dict(orient='records')
    #print (df)
    result.sort(key=lambda x:x['growth_rate'],reverse=True)
    return result

def get_diy_cn_index_data(index):
    df = ak.stock_zh_index_spot_sina()
    df2 = ak.fund_etf_spot_em()
    df['代码'] = df['代码'].apply(lambda x: x[2:8])
    #print (df2)
    #self.index_list=[i[2:8] for i in self.index_list]
    #df['代码'] = df['代码'].apply(lambda x: x[2:8])
    df.set_index('代码',inplace=True)
    df2.set_index('代码',inplace=True)

    df=df.loc[:,('名称','涨跌幅','成交额','最新价')]
    df2=df2.loc[:,('名称','涨跌幅','成交额','最新价')]
    df = pd.concat([df,df2])
    df=df[df.index.isin(index)].loc[:,('名称','涨跌幅','成交额','最新价')] 
    df['market']='cn'


    fmt_demical(df,['涨跌幅','成交额','最新价'])
    #df['成交额']=round(df['成交额']/100000000.,2)
    df=df.sort_values(by='涨跌幅',ascending=False)
    df.rename(columns={'涨跌幅':'涨幅'},inplace=True)
    #print (df)

    df = df.reset_index()
    df.rename(columns={'名称':'name','涨幅':'growth_rate','代码':'code','成交额':'turnover','最新价':'close'},inplace=True)
    #print (df)
    result = df.to_dict(orient='records')
    result.sort(key=lambda x:x['growth_rate'],reverse=True)
    return result
    #print (result)
    
def get_daily_market():    
    df = df_all.iloc[:,:]
    up_sum=(df['涨跌幅']>0).sum()
    up_sum_ratio=round(100.*(df['涨跌幅']>0).sum()/df.shape[0],2)
    down_sum=(df['涨跌幅']<0).sum()
    #down_sum=(df['涨跌幅']<0).sum()
    #long_10=round(100.*(df['涨跌幅']>=10).sum()/df.shape[0],2)
    #long_7=round(100.*df[(df['']<=10 && df['涨跌幅']>=7].sum()/df.shape[0],2)                                                
   # long_7=df[df["涨跌幅"].map(lambda x: ((x>=7) & (x<10)))].sum()   
    #long_7= round(100.*df[ df["涨跌幅"] >= 7 & df["涨跌幅"] < 10].sum()/df.shape[0],2)
    #long_7= round(100.*df[(df["涨跌幅"] >= 7) & (df["涨跌幅"] < 10)].shape[0]/df.shape[0],2)
    long_10=(df['涨跌幅']>=10).sum()  
    short_10=(df['涨跌幅']<=-10).sum()  
    _mean=round(df['涨跌幅'].mean(),1)
    _median=round(df['涨跌幅'].median(),1)
    data={"up_sum":up_sum,"up_sum_ratio":up_sum_ratio,"down_sum":down_sum,"long_10":long_10,"short_10":short_10,"mean":_mean,"median":_median}
    return data

def get_hkstock(hk_stock):
    df = ak.stock_hk_spot_em()
    df = df[df['代码'].isin(hk_stock)]
    df = df.loc[:,('代码','名称','涨跌幅','成交额','最新价')]    
    df['成交额']=df['成交额'].apply(lambda x: round(x/10000.,0))
    df.rename(columns={'代码':'code','成交额':'turnover','名称':'name','涨跌幅':'growth_rate','最新价':'close'},inplace=True)
    df['market'] = 'hk'
    list_df=df.to_dict('records')
    return list_df 

def create_html(index={},stock={},summary_text='',summary_end_text=''):
    #<ul><li>Coffee</li><li>Milk</li></ul>    
    #get_summary
    #print (index_info)
    #print (stock_info)
    
    bold_stocks=bold_stock_list
    temp_file=open("./template.html","r",encoding = 'utf-8')
    temp_str=temp_file.read() 
    stock_info=stock+get_hkstock(hk_stock_list)   
    stock_info.sort(key=lambda x:x['growth_rate'],reverse=True)
    #print (stock_info)
    temp_dict={'STOCK':stock_info,'INDEX':index}
    #print (temp_dict)
    msg_dict={'STOCK':'','INDEX':''}
#<font color="#FF0000">我是红色字体</font>
    for i,j in temp_dict.items():
    #sendmsg = date+' '+times
        sendmsg='' 
        ino=1
        for data in j: 
            #print (data)
            if float(data['growth_rate']) > 0 and float(data['growth_rate']) <=4 :
                _text_color="#CD5C5C"
            elif float(data['growth_rate']) > 4:
                #sendmsg += '<tr style="color: #FF4500;">'
                _text_color="#B22222"
            elif float(data['growth_rate']) < 0 and float(data['growth_rate']) >=-4 :
                #sendmsg += '<tr style="color: "#98FB98;">'
                _text_color="#3CB371"
            elif float(data['growth_rate']) < -4:
                #sendmsg += '<tr style="color: "#2E8B57;">'
                _text_color="#228B22"
            else:
                #sendmsg += '<tr style="color: "#FFFAF0;">'  
                _text_color="#000000"
            #print (type(data['code'][0:3]))
            #if i== "STOCK":
            if data['code'][0:3] in  ['600','601','688','603','510','512','515','513','516']:
                #print ('sh')
                market = 1
                _code=data['code'] 
                data['turnover']=float(data['turnover'])*1./100000000
                _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(market,_code) 
            elif data['code'][0:3] in ['300','301','002','399','159']:
                #print ('sz')
                market = 0
                _code=data['code'] 
                data['turnover']=float(data['turnover'])*1./100000000
                _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(market,_code) 
            elif data['code'][0:3] in ['000']:
                #print ('sz')
                if i=="STOCK":
                    market = 0
                elif i=="INDEX":
                    market = 1
                _code=data['code'] 
                data['turnover']=float(data['turnover'])*1./100000000
                _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(market,_code) 
            else:
                #print (data)
                if data['market'] == 'cn':
                    market = 0
                    _code=data['code']
                    data['turnover']=float(data['turnover'])*1.
                    if data['code'][0:2] ==  'sh':
                        market = 1
                        _code=data['code'][2:] 
                    elif data['code'][0:2] ==  'sz':
                        market = 0
                        _code=data['code'][2:] 
                        _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(market,_code)
                    else:
                        continue
                elif data['market'] == 'hk':
                    market=116
                    _code=data['code'] 
                    data['turnover']=float(data['turnover'])*1./10000
                    _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(market,_code)
                #elif data['market'] == 'cn':
                #    pass
                else :
                    print (data)
                    print ("market error!")
                    return
            if data['name'] in bold_stocks:
                sendmsg += '<tr style="color: {6};"><td><b>{0}</b></td><td><b><a href=\"{1}\" target=\"_blank\" style="color: {6};">{2}</a></b></td><td><b>{3}</b></td><td><b>{4}</b></td><td><b>{5}</b></td>'.format(ino, _url,data['name'],data['growth_rate'],data['close'] ,round(data['turnover'],2),_text_color)
            else:
                #sendmsg += "<td>{}</td><td>{}</td><td>{}</td><td>{}</td>".format(ino,data['name'],data['growth_rate'],round(float(data['turnover'])*1./10000,2))
                #sendmsg += "<td>{0}</td><td><a href=\"{1}\" target=\"_blank\"><font color=\"black\">{2}</font></a></td><td>{3}</td><td>{4}</td><td>{5}</td>".format(ino, _url,data['name'],data['growth_rate'],data['close'], round(data['turnover'],2))
                sendmsg += '<tr style="color: {6};"><td>{0}</td><td><a href=\"{1}\" target=\"_blank\" style="color: {6};">{2}</a></td><td>{3}</td><td>{4}</td><td>{5}</td>'.format(ino, _url,data['name'],data['growth_rate'],data['close'] ,round(data['turnover'],2),_text_color)
            sendmsg += '</tr>'
            ino+=1
        msg_dict[i]=sendmsg
        #print (html_str)
    #msg_dict['SUMMARY']=get_summary_all(index_info,config)
    msg_dict['SUMMARY']='🕔更新时间: '+summary_text
    html_str=Template(temp_str).safe_substitute(msg_dict)
    html_str+=summary_end_text
    with open("./stock.html",'w',encoding = 'utf-8') as f:
        f.write(html_str)
    f.close()



def get_url(_code):
    if _code[0:3] in  ['600','601','688','603','510','512','515','513','516']:
        _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(1,_code) 
    elif _code[0:3] in ['300','301','002','399','159']:
        _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(0,_code) 
    elif _code[0:3] in ['000']:
        _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(1,_code) 
    else:
        if _code[0:2] ==  'sh':
            _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(1,_code[2:])
        elif _code[0:2] ==  'sz':
            _url="https://wap.eastmoney.com/quote/stock/{}.{}.html".format(0,_code[2:])
        else:
            _url=''
            pass
    return _url


def pushplus(topic='me'):
    response=send_message(key=topic,_itype='file',_str='./stock.html',_title='自选股({})'.format(time.strftime('%m-%d', time.localtime(time.time()))),_template='html',_send_type='post')
    print ('Sent by pushplus!')      
        
def get_time():
    # 创建带UTC 0时区信息的当前时间
    utc_zero = datetime.now(timezone.utc)
    # print("UTC 0时区:", utc_zero)
    # 将UTC 0时区时间直接转换为北京时间
    beijing_now = utc_zero.astimezone(timezone(timedelta(hours=8)))
    # print("北京时间:", beijing_now)
    _date = beijing_now.strftime('%Y-%m-%d')
    _time = beijing_now.strftime('%H:%M:%S')
    return _date, _time

def get_summary(_index_info,_dict,config):
    daily_data=get_daily_market()
    index_info=_index_info
    #print (index_info)
    #index_info.set_index("日期", inplace=True)
    date, times = get_time()
    sendmsg=date+' '+times
    last_trade_day=bb.get_trade_day(1)  
    this_trade_day=bb.get_trade_day(0)
    for i in index_info:
        if i['name'] == '上证指数':            
            sh_money = float(i['turnover'])
            #print (sh_money)
        elif i['name'] == '深证成指':
            sz_money = float(i['turnover'])
            #print (sz_money)

    sendmsg+='<ul><li>💲 两市成交<font color=blue><strong>{0}</strong></font>亿, 量比<font color=blue><strong>{1}</strong></font>,涨幅中位数<font color=blue><strong>{4}%</strong></font>,涨幅均值<font color=blue><strong>{5}%</strong></font>,北向<font color=blue><strong>{8}</strong></font>亿,南向资金<font color=blue><strong>{9}</strong></font>亿.</br>💲 上涨<font color=red><strong>{2}</strong></font>家,下跌<font color=green><strong>{3}</strong></font>家,涨停<font color=red><strong>{6}</strong></font>家,跌停<font color=green><strong>{7}</strong></font>家.</br>💲 <strong>十大热股</strong>: <font color=black>{10}</font>. </br>💲  <strong>创新高</strong>: <font color=black>{11}</font></li>'.format(round(sh_money+sz_money),_dict['money_ratio'],daily_data['up_sum'],daily_data['down_sum'],daily_data['median'],daily_data['mean'],daily_data['long_10'],daily_data['short_10'],_dict['北向'],_dict['南向'],','.join(_dict['hot']),','.join(_dict['cxg'])) 
    ####"#FF00FF" 粉色
    return sendmsg

def get_stocks():
    df = df_all.iloc[:,:]
    df = df.loc[:,['代码','名称','最新价','涨跌幅','成交额','振幅','换手率','市盈率-动态','市净率','总市值','流通市值','60日涨跌幅','年初至今涨跌幅']]
    df = df.dropna(axis=0, how='any')
    
    max_money=df.sort_values(by="成交额",ascending=False).head(20)
    max_change_pct=df.sort_values(by="涨跌幅",ascending=False).head(20)
    min_change_pct=df.sort_values(by="涨跌幅",ascending=True).head(20) 
    turnover=df.sort_values(by="换手率",ascending=False).head(20)
    net_value=df.sort_values(by="总市值",ascending=False).head(20)
    amp=df.sort_values(by="振幅",ascending=False).head(20)   
    max_money=format_stock_data(max_money)
    max_change_pct=format_stock_data(max_change_pct)
    min_change_pct=format_stock_data(min_change_pct)
    turnover=format_stock_data(turnover)
    net_value=format_stock_data(net_value)
    amp=format_stock_data(amp)

    return df

def get_growth_color(num):
    return "#3CB371" if num < 0 else "#CD5C5C" if num > 0 else "black"

def summary(index_info,_dict):
    date, times = get_time()
    sendmsg=date+' '+times+' \n'
    last_trade_day=get_trade_day(1)  
    this_trade_day=get_trade_day(0)
    sh_money=sz_money=bz_money=0.
    for i in index_info:
        if i['name'] == '上证指数':
            sh_money = float(i['turnover'])/100000000.
        elif i['name'] == '深证成指':
            sz_money = float(i['turnover'])/100000000.
        elif i['name'] == '北证50':
            bz_money = float(i['turnover'])/100000000.

        
        
    daily_data=get_daily_market()
    df=get_stocks()
    #df.to_csv('data.csv')
    #df=pd.read_csv('data.csv')
    
    up_rows=df[df['涨跌幅']>0].shape[0]
    down_rows=df[df['涨跌幅']<0].shape[0]
    
    sendmsg+='&#9210; <b>成交</b>: 共 <font color=blue><strong>{0}</strong></font> 亿, 量比 <font color=blue><strong>{1}</strong></font>, 南向 <font color=blue><strong>{2}</strong></font> 亿</br>'.format(round(sh_money+sz_money,2),round(_dict['money_ratio'],2),_dict['南向'])
   
    sendmsg+='&#9210; <b>涨跌</b>: 上涨 <font color="#CD5C5C"><strong>{0}</strong></font>,下跌 <font color="#3CB371"><strong>{1}</strong></font>, 涨停 <font color="#CD5C5C"><strong>{2}</strong></font>, 跌停 <font color="#3CB371"><strong>{3}</strong></font></br>'.format(up_rows,down_rows,daily_data['long_10'],daily_data['short_10'])
    sendmsg+='&#9210; <b>涨幅</b>: 均值 <font color={2}><strong>{0}%</strong></font>, 中位数 <font color={3}><strong>{1}%</strong></font></br>'.format(round(df['涨跌幅'].mean(),1), round(df['涨跌幅'].median(),1),get_growth_color(df['涨跌幅'].mean()),get_growth_color(df['涨跌幅'].median()))
       
    df_stock = df_all.iloc[:,:]
    df_stock = df_stock.dropna(axis=0, how='any')
    df_stock['行情']=df_stock[["名称","涨跌幅","成交额"]].apply(lambda x:str(x["名称"])+'('+str(round(x["涨跌幅"],1))+'%,'+str(round(x["成交额"]/100000000.,1))+'亿)',axis=1)
    #money_list= df_stock.sort_values(by="成交额",ascending=False).head(5)['行情'].to_list()
    money = df_stock.sort_values(by="成交额",ascending=False).head(20).reset_index(drop=True)

    money['成交额']=money['成交额'].apply(lambda x: round(x/100000000.,2))
    money['总市值']=money['总市值'].apply(lambda x: int(x/100000000))
    
    
    thx =ak.stock_board_industry_summary_ths().loc[:,('板块','涨跌幅','总成交额','净流入','上涨家数','下跌家数','领涨股','领涨股-最新价', '领涨股-涨跌幅')]    
    thx = thx.sort_values(by='涨跌幅',ascending=False)
    thx['行情']=thx[["板块","涨跌幅"]].apply(lambda x:str(x["板块"])+'('+str(x["涨跌幅"])+'%)',axis=1)
    thx_up_list=thx.head(5)['行情'].to_list()
    thx_down_list=thx.tail(5)['行情'].to_list()
    thx_up=thx.head(5)[["板块","涨跌幅"]]
    thx_down=thx.tail(5)[["板块","涨跌幅"]].reset_index(drop=True)
    #thx_down=thx_down.sort_values(by='涨跌幅',ascending=False)
   
    # money_str=''
    # thx_up_str=''
    # thx_down_str=''
    
  
    # for i in money_list:
    #     money_str+=i
    #     money_str+=' '
    # money_str=','.join(money_list)
    
    #sendmsg+='&#9210;成交额最大: <font color=blue>{0}</font></br>'.format(money_str)
    # for i in thx_up_list:
    #     thx_up_str+=i
    #     thx_up_str+=' '
    # thx_up_str=','.join(thx_up_list) 
    # sendmsg+='&#9210;板块领涨: <font color="#FF0000">{0}</font></br>'.format(thx_up_str)
    # for i in thx_down_list:
    #     thx_down_str+=i
    #     thx_down_str+=' '
    # thx_down_str=','.join(thx_down_list)
    # sendmsg+='&#9210;板块领跌: <font color="#2E8B57">{0}</font></br>'.format(thx_down_str)
    sendmsg+='&#9210; <b>板块概况</b>'
    sendmsg+='<table border="1" align="center" cellpadding="10" cellspacing="0"><tr><th style="width: 40px" rowspan="2">序号</th><th style="width: 190px;color:#CD5C5C" colspan="2">领涨</th><th style="width: 190px;color:#3CB371"colspan="2">领跌</th></tr><tr><th style="width: 120px">板块</th><th style="width: 70px">涨幅(%)</th><th style="width: 120px">板块</th><th style="width: 70px">涨幅(%)</th></tr>'
    for ii in range(0,5):
        #print (ii)
        sendmsg+='<tr><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(ii+1,thx_up.loc[ii,'板块'],thx_up.loc[ii,'涨跌幅'],thx_down.loc[4-ii,'板块'],thx_down.loc[4-ii,'涨跌幅'])
    sendmsg+='</table>'
    
    sendmsg+='&#9210; <b>10大成交额</b>'
    #sendmsg+='<table border="1" align="center" cellpadding="10" cellspacing="0"><table><tr><th style="width: 30px">序号</th><th style="width: 80px">股票名称</th><th style="width: 60px">成交额(亿)</th><th style="width: 50px">涨幅(%)</th><th style="width: 50px">振幅(%)</th><th style="width: 50px">量比</th><th style="width: 50px">换手率</th><th style="width: 60px">总市值(亿)</th></tr>'
    #sendmsg+='<table border="1" align="center" cellpadding="10" cellspacing="0"><table><tr><th style="width: 30px">序</th><th style="width: 80px">股票</th><th style="width: 60px">成交额</th><th style="width: 50px">涨幅</th><th style="width: 50px">振幅</th><th style="width: 50px">量比</th><th style="width: 50px">换手</th><th style="width: 60px">总市值</th></tr>'
    sendmsg+='<table border="1" align="center" cellpadding="10" cellspacing="0"><table><tr><th style="width: 30px">序</th><th style="width: 80px">股票</th><th style="width: 60px">成交额</th><th style="width: 50px">涨幅</th><th style="width: 50px">振幅</th><th style="width: 50px">量比</th><th style="width: 50px">换手</th><th style="width: 60px">总市值</th></tr>'
    for ii in range(0,10):
        print (ii)
        _color=get_growth_color(money.loc[ii,'涨跌幅'])
        #sendmsg+='<tr style="color: {};" ><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'.format(_color,ii+1,money.loc[ii,'名称'],int(money.loc[ii,'成交额']),money.loc[ii,'涨跌幅'],money.loc[ii,'振幅'],money.loc[ii,'量比'],money.loc[ii,'换手率'],money.loc[ii,'总市值'])
        sendmsg+='<tr style="color: {0};" ><td>{1}</td><td><a href=\"{9}\" target=\"_blank\" style="color: {0};">{2}</a></td><td>{3}</td><td>{4}</td><td>{5}</td><td>{6}</td><td>{7}</td><td>{8}</td></tr>'.format(_color,ii+1,money.loc[ii,'名称'],int(money.loc[ii,'成交额']),money.loc[ii,'涨跌幅'],money.loc[ii,'振幅'],money.loc[ii,'量比'],money.loc[ii,'换手率'],money.loc[ii,'总市值'],get_url(money.loc[ii,'代码']))
    sendmsg+='</table>'
    
    
#    <a href=\"{1}\" target=\"_blank\" style="color: {6};">
    
    endmsg='&#9210;<strong>十大热股</strong>: <font color=black>{0}</font></br>'.format(','.join(_dict['hot']))
    endmsg+='&#9210;<strong>创新高票</strong>: <font color=black>{0}</font></br>'.format(','.join(_dict['cxg']))
    
    
    

    
    
    #subscribe_list = ak.futures_foreign_commodity_subscribe_exchange_symbol()
    #df_futures =  ak.futures_foreign_commodity_realtime(subscribe_list=subscribe_list)
    #df_futures['振幅']= round((df_futures['最高价']-df_futures['最低价'])*100/df_futures['昨日结算价'],2)
    #df_futures['涨跌幅']= round(df_futures['涨跌幅'],2)   
    
    #print (sendmsg)
    #print ("##################")
    
    return sendmsg,endmsg


################# add 2023/10/16 ###############################  
def update_json(_dict,date_str):
    if get_today_trade_status():
        filename="data.json"
        target='./archive/{}'.format(filename)
        old_json=get_old_data(target)
        f2 = open(filename, 'w')
        temp_dict={date_str:_dict}
        old_json.update(temp_dict)
        new_json = json.dumps(old_json)       
        f2 = open(target, 'w')
        f2.write(new_json)
        f2.close()
    else:
        print ("今日不是交易日")
        pass
    
def add_today(index_rawdata):    
    filename="data.json"
    target='./archive/{}'.format(filename)
    old_json=get_old_data(target)
    today=get_trade_day()
    last_day=get_trade_day(1)
    #######################################
    total_money=0
    for i in index_rawdata:
        #print (i)
        if i['code'] == '000001' or  i['code'] == '399001':
            total_money+=round(float(i['turnover'])*1./100000000,2)
            #print (total_money)
    if last_day in old_json:
        money_ratio=total_money/old_json[last_day]['total_money']
    else:
        money_ratio=-1
    _dict={'total_money':round(total_money,2),'money_ratio':round(money_ratio,2),'data':index_rawdata}
    ########################################
    hsgt_df = ak.stock_hsgt_fund_flow_summary_em()
    grouped=hsgt_df.groupby('资金方向')
    for label, option_course in grouped:
        #print (label,round(option_course['成交净买额'].sum(),2))
        _dict[label]=round(option_course['成交净买额'].sum(),2)
    #######################################
    hot_df = ak.stock_hot_rank_wc(date=time.strftime('%Y%m%d', time.localtime(time.time())))
    hot_list=hot_df.head(10)['股票简称'].to_list()
    _dict["hot"]=hot_list
    ########################################
    cxg_df = ak.stock_rank_cxg_ths(symbol="历史新高")
    cxg_list=cxg_df.head(10)['股票简称'].to_list()
    _dict["cxg"]=cxg_list
    
    return _dict
   
def get_today_index(index_rawdata):
    _dict=add_today(index_rawdata)
    return _dict    
       
def get_old_data(filename):
    if os.path.exists(filename):
        try:
            with open(filename,'r') as fp:
                json_data = json.load(fp)
                return json_data
        except json.decoder.JSONDecodeError:
            return {}
    else:
        with open(filename,'w') as fp:
            return {}



@timer_decorator 
def main(topic):
    print ('Start topic: {}'.format(topic))
    if not get_today_trade_status():
        print ("今日不是交易日")
        return
    else:
        print ("今天是交易日")

    # print ('Entering proxy...')
    # test_proxy()
    #use_proxy()
    print ("\nInfo: stock")
    stock=get_diy_stock_data(stock_name_diy_list)
    print (stock)
    time.sleep(10)
    print ("\nInfo: index")
    index=get_diy_cn_index_data(index_diy_list)
    print (index)
    #time.sleep(60)
    print ("\nInfo: archive")
    _dict=add_today(index)
    date_str=get_trade_day(0)
    update_json(_dict,date_str)
    #time.sleep(120)
    print ("\nInfo: summary")
    summary_text,summary_end_text=summary(index,_dict)
    print ("\nInfo: html")
    create_html(index,stock,summary_text,summary_end_text)
    pushplus(topic)


def only_send(topic):
    send_message(key=topic,_itype='file',_str='./stock.html',_title='test({})'.format(time.strftime('%m-%d', time.localtime(time.time()))),_template='html',_send_type='post')

if __name__ == '__main__':
    if len(sys.argv) == 1:
        main('me')
        #only_send('me')

    else:
        para_argv=sys.argv[1][1:]
        #main(para_argv,1)
        main(para_argv)
