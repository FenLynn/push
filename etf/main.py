import sys
sys.path.append("..")
from cloud import *
from cloud.utils.lib import *

etf_spts={'159920':[1.2,1.18,1.13],'510050':[2.707,2.571,2.487],'510300':[4.01,3.7],'513050':[1.213,1.157],'512480':[0.891,0.77],'512890':[1.097,1.080,1.050,1.03]}

url_dict={
    "510050":"\n![上证50ETF](https://image.sinajs.cn/newchart/macd/n/sh510050.gif)",
    "513050":"\n![中概ETF](https://image.sinajs.cn/newchart/macd/n/sh513050.gif)",
    "512480":"\n![半导体ETF](https://image.sinajs.cn/newchart/macd/n/sz159813.gif)",
    "159920":"\n![恒生ETF](https://image.sinajs.cn/newchart/hk_stock/daily/HSI.gif)",
    "510300":"\n![沪深3000ETF](https://image.sinajs.cn/newchart/macd/n/sh000300.gif)",
    "512890":"\n![红利低波ETF](https://image.sinajs.cn/newchart/macd/n/sh512890.gif)"
}

def get_spt_growth(df):
    msg=''
    #result = df.to_dict(orient='records')
    df = df.reset_index()
    # 按'score'列降序排序 
    df = df.sort_values(by='涨幅(%)',  ascending=False)
    result = df.to_dict(orient='records')
    result.sort(key=lambda x:x['涨幅(%)'],reverse=True)
    data=[]
    for etf in result:
        if etf['代码'] in etf_spts and len(etf_spts[etf['代码']]) > 0:
            data.append({'代码':etf['代码'],'名称':etf['名称'],'目标价':str(etf['最新价'])+'(现价)','名称':etf['名称'],'价差比(%)':0,'涨幅(%)':etf['涨幅(%)']})
            for i in etf_spts[etf['代码']]:
                temp_s={'代码':etf['代码'],'名称':etf['名称'],'目标价':i,'名称':etf['名称'],'价差比(%)':round((i-etf['最新价'])*100/etf['最新价'],2),'涨幅(%)':etf['涨幅(%)']}
                data.append(temp_s)
    data=pd.DataFrame(data)
    print (data)
    grouped = data.groupby('名称')
    for name,group in grouped:
        code = str(group['代码'].to_list()[0])
        #print (code)
        money = df[df['代码'] == code]['成交额(亿)'].values[0]
        growth = df[df['代码'] == code]['涨幅(%)'].values[0]
        price = df[df['代码'] == code]['最新价'].values[0]

        #print (money)
        group=group.sort_values(by='价差比(%)',ascending=False)
        group=group.reset_index(drop=True)
        group.index=group.index+1
        color_df(group,key_column='价差比(%)',code=group['代码'].to_list()[0])
        group = group.drop(['代码','涨幅(%)'], axis=1)
        #print (group.to_markdown()) 
        #f.write(f'#### {name} \n')

        mycolor = 'red' if growth > 0 else  'green' if growth < 0 else 'black'
        msg+=f'######   ⏺ [**{name}({code})**]({get_url(code)}): <font color={mycolor}>**{price} / {money}亿 / {growth}%**</font>  \n'
        msg+=group.to_markdown(index=True,tablefmt="github")
        msg+='\n\n'
        msg+=url_dict[code]
        msg+='\n'
        #f.write(f'######   ⏺{name}({code}), <font color={mycolor}>**{money}亿 {growth}%**</font>  \n')
        #f.write(group.to_markdown(index=True,tablefmt="github"))
        #f.write('\n')
    #f.write(msg)
    #f.close()
#    print (data)
    return msg

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

def get_diy_cn_index_data_old():
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
    #df=df[df.index.isin(index)].loc[:,('名称','涨跌幅','成交额','最新价')] 
    df['market']='cn'
    fmt_demical(df,['涨跌幅','成交额','最新价'])
    #df['成交额']=round(df['成交额']/100000000.,2)
    df=df.sort_values(by='涨跌幅',ascending=False)
    df.rename(columns={'涨跌幅':'涨幅'},inplace=True)
    df = df.reset_index()
    df.rename(columns={'名称':'name','涨幅':'growth_rate','代码':'code','成交额':'turnover','最新价':'close'},inplace=True)

    return df

def get_diy_cn_index_data():
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
    #df=df[df.index.isin(index)].loc[:,('名称','涨跌幅','成交额','最新价')] 
    #df['market']='cn'
    fmt_demical(df,['涨跌幅','成交额','最新价'])
    df['成交额']=round(df['成交额']/100000000.,2)
    df=df.sort_values(by='涨跌幅',ascending=False)
    df.rename(columns={'涨跌幅':'涨幅(%)','成交额':'成交额(亿)'},inplace=True)
    #df = df.reset_index()
    print (df)
    #df.set_index('代码',inplace=True)
    #df.rename(columns={'名称':'name','涨幅':'growth_rate','代码':'code','成交额':'turnover','最新价':'close'},inplace=True)
    #result = df.to_dict(orient='records')
    #result.sort(key=lambda x:x['growth_rate'],reverse=True)
    return df

# def get_css(cssfile=css_file):
#     with open(cssfile,  'r', encoding='utf-8') as src:
#         content = src.read()
#     return content


def get_impt_index(df):
    #print (df)
    msg=''
    impt_index=['000001','399006','399001','399303']
    df=df[df.index.isin(impt_index)]
    #df=df[df.index.isin(impt_index)].loc[:,('名称','涨跌幅','成交额','最新价')] 
    color_df(df,key_column='涨幅(%)')
    df=df.reset_index(drop=True)
    #group = group.drop(['代码'], axis=1)
    # f=open('./etf.md','w',encoding='utf8')
    # f.write(df.to_markdown(index=False))
    # f.close()
    msg+='######  ⏺ **重要指数** \n'
    msg+=df.to_markdown(index=False,tablefmt="github")
    msg+='\n\n'
    msg+="![上证](https://image.sinajs.cn/newchart/min/nsh000001.gif) \n"
    msg+="![上证](https://image.sinajs.cn/newchart/macd/n/sh000001.gif) \n"
    #print (df)
    return msg

def create_md(msg=[]):
    f=open('./etf.md','w',encoding='utf8')
    f.write('🕔更新时间:{0} \n'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))
    f.write(get_css())
    for i in msg:
        f.write(i)
    f.close()

def create_html(data,result):  #没用
    _today=datetime.today().strftime('%Y-%m-%d')
    _tomorrow=(datetime.now()+timedelta(days=1)).strftime('%Y-%m-%d')    
    current_time_=time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))
    #print (result)

    for i in result:
        if i['code'] == '000001':
            sh_close=i['close']
            sh_growth=i['growth_rate']
            #beta = 999 if alpha > 7 else 99 if alpha == 7 else 0
            sh_color= 'red' if sh_growth > 0 else 'green' if sh_growth <0 else 'black'
        elif i['code'] == '399006':
            cyb_close=i['close']
            cyb_growth=i['growth_rate']  
            cyb_color= 'red' if cyb_growth > 0 else 'green' if cyb_growth <0 else 'black'
        elif i['code'] == '399001':
            sz_close=i['close']
            sz_growth=i['growth_rate']  
            sz_color= 'red' if sz_growth > 0 else 'green' if sz_growth <0 else 'black'
        elif i['code'] == '399303':
            gz_close=i['close']
            gz_growth=i['growth_rate']  
            gz_color= 'red' if gz_growth > 0 else 'green' if gz_growth <0 else 'black'
        else:
            pass
    f=open('./etf.md','w',encoding='utf8')

    f.write('🕔更新时间:{0}<br/>'.format(current_time_))
    f.write(get_css())
    f.write('上证: <font color= {0}> {1}({2}%)</font>, 创业板: <font color= {6}> {7}({8}%)</font> </br>深证: <font color= {3}> {4}({5}%)</font>, 国证2000: <font color= {9}> {10}({11}%)</font><br/></br>'.format(sh_color,sh_close,sh_growth,sz_color,sz_close,sz_growth,cyb_color,cyb_close,cyb_growth, gz_color,gz_close,gz_growth))
    #f.write('上证: <font color= {0}> {1}( {2}% )</font>,  创业板: <font color= {3}> {4}( {5}% )</font> <br/>'.format(sh_color,sh_close,sh_growth,cyb_color,cyb_close,cyb_growth))
    for i in data:
        if i['growth_rate'] < 0:
            f.write('⏺ **{0}**, {1}, 现价 <font color= green>**{2}</font> (涨幅<font color= green>{3}%**</font>) :<br/>'.format(i['name'],i['code'],i['close'],i['growth_rate']))
        elif  i['growth_rate'] > 0:
            f.write('⏺ **{0}**, {1}, 现价 <font color= red>**{2}</font>  (涨幅<font color= red>{3}%**</font>)  :<br/>'.format(i['name'],i['code'],i['close'],i['growth_rate']))
        else:
            f.write('⏺ **{0}**, {1}, 现价 <font color= black>**{2}</font> (涨幅<font color= black>{3}%**</font>) :<br/>'.format(i['name'],i['code'],i['close'],i['growth_rate']))
        for j in range(len(i['ispt'])):
            jcolor= 'indianred' if i['rate'][j] > 0 else 'royalblue' if i['rate'][j] <0 else 'black'  
            f.write('💰价位{0} : <font color= {3}>{1}</font>, 现价涨跌 <font color= {3}> {2}% </font> 到位 <br/>'.format(j+1,i['ispt'][j],i['rate'][j],jcolor))
        f.write('<br/>')
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

def color_df_old(df,key_column='',code=''):
    #print (df)
    for row in df.index:
        # if code == '':
        #     url=get_url(row)
        # else:
        #     url=get_url(code)
        if df.loc[row][key_column] < 0:
            df.loc[row,:]=df.loc[row,:].apply(lambda x:  f'<font color=teal>{x}</font>')
            df.at[row,'名称']='[{0}]({1})'.format(df.loc[row]['名称'],url)
        elif df.loc[row][key_column] > 0:
            df.loc[row,:]=df.loc[row,:].apply(lambda x:  f'<font color=red>{x}</font>')
            df.at[row,'名称']='[{0}]({1})'.format(df.loc[row]['名称'],url)
        else:
            df.loc[row,:]=df.loc[row,:].apply(lambda x:  f'<font color=black>{x}</font>')
            df.at[row,'名称']='[{0}]({1})'.format(df.loc[row]['名称'],url)
            pass

def color_df(df,key_column='',code=''):
    #print (df)
    for row in df.index:
        # if code == '':
        #     url=get_url(row)
        # else:
        #     url=get_url(code)
        if df.loc[row][key_column] < 0:
            df.loc[row,:]=df.loc[row,:].apply(lambda x:  f'<font color=teal>{x}</font>')
            df.at[row,'名称']='{0}'.format(df.loc[row]['名称'])
        elif df.loc[row][key_column] > 0:
            df.loc[row,:]=df.loc[row,:].apply(lambda x:  f'<font color=red>{x}</font>')
            df.at[row,'名称']='{0}'.format(df.loc[row]['名称'])
        else:
            df.loc[row,:]=df.loc[row,:].apply(lambda x:  f'<font color=black>{x}</font>')
            df.at[row,'名称']='{0}'.format(df.loc[row]['名称'])
            pass

def main(topic='me'):
    print ('Start topic: {}'.format(topic))
    if not get_today_trade_status():
        print ("今日不是交易日")
        return
    else:
        print ("今天是交易日")
    df=get_diy_cn_index_data()
    msg1=get_impt_index(df)
    msg2=get_spt_growth(df)
    create_md([msg1,msg2])
    pushplus(topic)
    pass
    
def pushplus(topic='me'):
    response=send_message(key=topic,_itype='file',_str="./etf.md",_title='ETF({})'.format(time.strftime('%H:%M', time.localtime(time.time()))),_template='markdown',_send_type='post')
    #response=send_message(key=topic,_itype='file',_str="./test.md",_title='ETF({})'.format(time.strftime('%Y-%m-%d', time.localtime(time.time()))),_template='markdown',_send_type='post')
    print (response)
    print ('Sent by pushplus!')         

def only_send(topic='me'):
    response=send_message(key=topic,_itype='file',_str="./etf.md",_title='ETF({})'.format(time.strftime('%H:%M', time.localtime(time.time()))),_template='markdown',_send_type='post')
    print ('Sent by pushplus!')         


if __name__ == '__main__':
    if len(sys.argv) == 1:
        main('me')
        #only_send('me')
    else:
        para_argv=sys.argv[1][1:]
        main(para_argv)
