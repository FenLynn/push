import sys 
sys.path.append("..") 
from cloud import *
from cloud.utils.lib import *

def get_growth_color(num):
    return "#3CB371" if num < 0 else "#CD5C5C" if num > 0 else "black"

def get_us_index():
    df = ak.index_global_spot_em()
    df = df[df['代码'].isin(['BDI','VNINDEX','RTS','SENSEX','GDAXI','MCX','NDX','UDI','SX5E','FCHI','N225','SPX','DJIA'])].reset_index(drop=True)
    sendmsg=''
    table_head='<table><tr  align=center><th style=\"min-width:20px\">序</th><th style=\"min-width:150px\">名称</th><th style=\"min-width:50px\">涨跌幅</th><th style=\"min-width:50px\">振幅</th><th style=\"min-width:110px\">更新时间</th></tr>${CONTENT}</table>'
    _bold_list=['UDI','NDX','SPX','DJIA']
    for i in df.index:
        _time=datetime.strptime(df.loc[i,'最新行情时间'],"%Y-%m-%d %H:%M:%S").strftime("%m/%d %H:%M:%S")
        if df.loc[i,'代码'] in _bold_list:
            sendmsg+='<tr><td align="center"><b>{1}</b></td><td align="center"><b>{2}</b></td><td><font color={0}><b>{3}</b></font></td><td align="center"><b>{4}</b></td><td align="center"><b>{5}</b></td></tr>'.format(get_growth_color(df.loc[i,'涨跌幅']),i+1,df.loc[i,'名称'],df.loc[i,'涨跌幅'],df.loc[i,'振幅'],_time)
        else:
            sendmsg+='<tr><td align="center">{1}</td><td align="center">{2}</td><td><font color={0}>{3}</font></td><td align="center">{4}</td><td align="center">{5}</td></tr>'.format(get_growth_color(df.loc[i,'涨跌幅']),i+1,df.loc[i,'名称'],df.loc[i,'涨跌幅'],df.loc[i,'振幅'],_time)
    html_str=Template(table_head).safe_substitute({'CONTENT':sendmsg})
    return html_str


def get_us_stock():
    df=ak.stock_us_spot_em()
    #df=pd.read_csv('us.csv')
    df=df.sort_values(by='涨跌幅',ascending=False)
    table_head='<table><tr  align=center><th style=\"min-width:25px\">序</th><th style=\"min-width:120px\">名称</th><th style=\"min-width:55px\">涨跌幅</th><th style=\"min-width:55px\">成交额</th><th style=\"min-width:55px\">市盈率</th><th style=\"min-width:60px\">总市值</th></tr>${CONTENT}</table>'
    #_us_stock=['105.AAPL','105.MSFT','105.NVDA','105.AMZN','105.GOOG','105.META','106.TSM','105.TSLA','106.BRK_A','106.BABA','106.PDD','106.JD','106.BILI','106.ONC','106.EDU','106.BAC','106.KO']
    _us_stock=['105.KHC','105.AAPL','105.MSFT','105.NVDA','105.AMZN','105.GOOG','105.META','106.TSM','105.TSLA','106.BRK_A','106.BABA','106.PDD','106.JD','106.BILI','106.ONC','106.EDU','106.BAC','106.KO','105.NFLX','106.AXP','106.GS','106.PFE','106.BLK','106.BA','106.LMT','105.AXP','106.OXY','106.MCO','106.CB ']
    df = df[df['代码'].isin(_us_stock)].reset_index(drop=True)
    df['成交额']=df['成交额'].apply(lambda x: round(x/100000000.,2))
    df['总市值']=df['总市值'].apply(lambda x: int(x/100000000))
    _bold_list=['105.AAPL','105.NVDA','105.TSLA','106.BABA']
    sendmsg=''
    for i in df.index:
        if df.loc[i,'代码'] in _bold_list:
            print ('yes')
            sendmsg+='<tr><td align="center"><b>{1}</b></td><td align="center"><b>{2}</b></td><td><font color={0}><b>{3}</b></font></td><td align="center"><b>{4}</b></td><td align="center"><b>{5}</b></td><td align="center"><b>{6}</b></td></tr>'.format(get_growth_color(df.loc[i,'涨跌幅']),i+1,df.loc[i,'名称'],df.loc[i,'涨跌幅'],df.loc[i,'成交额'],df.loc[i,'市盈率'],df.loc[i,'总市值'])
        else:
            print ('no')
            sendmsg+='<tr><td align="center">{1}</td><td align="center">{2}</td><td><font color={0}>{3}</font></td><td align="center">{4}</td><td align="center">{5}</td><td align="center">{6}</td></tr>'.format(get_growth_color(df.loc[i,'涨跌幅']),i+1,df.loc[i,'名称'],df.loc[i,'涨跌幅'],df.loc[i,'成交额'],df.loc[i,'市盈率'],df.loc[i,'总市值'])
    html_str=Template(table_head).safe_substitute({'CONTENT':sendmsg})
    return html_str




def create_html(html_name='./night.html',index_str='',stock_str=''):
    html_head='<html><head><style>.grid-container {display: grid;grid-template-columns: repeat(2, 1fr); gap: 5px;}table th {font-weight: bold; text-align: center !important; background: rgba(158,188,226,0.2); white-space: wrap;}table tbody tr:nth-child(2n) { background-color: #f2f2f2;}table{text-align: center;font-family: Arial, sans-serif; font-size: 15px;}</style><meta charset="utf-8"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing="5"}td,th {border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head>'
    data=open(html_name,'w',encoding='utf8')
    data.write(html_head)
    data.write('🕔更新时间:{0} \n'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))
    if index_str:
        data.write('📈 <font color= blue><b>夜盘指数</b></font>\n')
        data.write(index_str)
        data.write('<img src="https://image.sinajs.cn/newchart/usstock/min/IXIC.gif"/>')
    if stock_str:
        data.write('\n📈 <font color= blue><b>夜盘股票</b></font>\n')
        data.write(stock_str)
        data.write('<div class="grid-container"><img src="https://image.sinajs.cn/newchart/usstock/min/TSLA.gif"/><img src="https://image.sinajs.cn/newchart/usstock/min/nvda.gif"/></div>')
        data.write('<div class="grid-container"><img src="https://image.sinajs.cn/newchart/usstock/min/AAPL.gif"/><img src="https://image.sinajs.cn/newchart/usstock/min/BABA.gif"/></div>')

    data.write('</html>')
    data.close()


def pushplus(topic='me'):
    send_message(key=topic,_itype='file',_str="night.html",_title='夜盘股市({})'.format(time.strftime('%m-%d', time.localtime(time.time()))),_template='html')
    print ('Sent by pushplus!')

@timer_decorator
def main(topic='me'):
    print ('Start topic: {}'.format(topic))
    if is_use_proxy:
        use_proxy()
    index_str=get_us_index()
    stock_str=get_us_stock()
    create_html(index_str=index_str,stock_str=stock_str)
    pushplus(topic=topic)
    print ('{0}: Completed!'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))

if __name__ == '__main__':
    if len(sys.argv) == 1:
        main('me')
        #test()
    else:
        para_argv=sys.argv[1][1:]
        main(para_argv)

