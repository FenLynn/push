import sys 
sys.path.append("..") 
from cloud import *
from cloud.utils.lib import *

def get_growth_color(num):
    return "#3CB371" if num == "低估" else "#CD5C5C" if num == "高估" else "#F4A460" if num == "正常" else "white"


def get_fund_data():
    def get_index_valuation():
        """通过蛋卷基金API获取主要指数估值数据"""
        url = "https://danjuanapp.com/djapi/index_eva/dj"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        }
        
        try:
            response = requests.get(url, headers=headers, timeout=10)
            response.raise_for_status()
            data = response.json()
            return data['data']['items']
        except Exception as e:
            print(f"请求失败: {e}")
            return None

    def process_data(items):
        """处理并过滤所需指数数据"""
        #target_indices = ['上证50', '沪深300', '中证500']
        results = []
        
        for item in items:
            #if item['name'] in target_indices:
            results.append({
                "指数": item['name'],
                "PE": round(item['pe'], 1),
                "PE百分位": round(item['pe_percentile'] * 100, 1),
                "PB": round(item['pb'], 1),
                "PB百分位": round(item['pb_percentile'] * 100, 1),
                "ROE": round(item['roe'] * 100, 1),
                "股息率": round(item['yeild'] * 100, 1),
                "估值": "高估" if item['eva_type_int'] == 2 else "正常" if  item['eva_type_int'] == 1 else "低估" if item['eva_type_int'] == 0 else "异常",
                "链接": item['url'],
                "更新日期": item['date'],
                "代码": item['index_code']
            })
        return pd.DataFrame(results)


    """主程序"""
    print("正在获取指数估值数据...")
    items = get_index_valuation()
    
    if not items:
        print("数据获取失败，请检查网络连接")
        return None

    print("\n最新估值数据：")
    df = process_data(items)
    df.to_csv('./data.csv')
    df = pd.read_csv('./data.csv')
    return df


def create_html(html_name='./fund.html',df=pd.DataFrame()):
    html_head='<html><head><style>.grid-container {display: grid;grid-template-columns: repeat(2, 1fr); gap: 5px;}table th {font-weight: bold; text-align: center !important; background: rgba(158,188,226,0.2); white-space: wrap;} table{text-align: center;font-family: Arial, sans-serif; font-size: 15px;}</style><meta charset="utf-8"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing="5"}td,th {border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head>'
    data=open(html_name,'w',encoding='utf8')
    data.write(html_head)
    data.write('🕔更新时间:{0} \n'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))
    # table_head='<table><tr  align=center><th style=\"min-width:25px\">序</th><th style=\"min-width:120px\">指数</th><th style=\"min-width:55px\">PE</th><th style=\"min-width:55px\">PB</th><th style=\"min-width:55px\">PE百分位</th><th style=\"min-width:60px\">PB百分位</th><th style=\"min-width:60px\">ROE</th><th style=\"min-width:60px\">股息率</th><th style=\"min-width:60px\">估值</th></tr>${CONTENT}</table>'
    table_head='<table><tr  align=center><th style="min-width:25px">序</th><th style="min-width:85px">指数</th><th style="min-width:40px">PE</th><th style="min-width:40px">PB</th><th style="min-width:45px">PE百分位</th><th style="min-width:40px">PB百分位</th><th style="min-width:40px">ROE</th><th style="min-width:40px">股息率</th><th style="min-width:40px">估值</th></tr>${CONTENT}</table>'
    _bold_list=['创业板','沪深300','全指医药','恒生指数','上证50','中证500','中证银行','红利低波','证券公司','纳指100','科创50']
    if not df.empty:
        # str_df=df.to_html()
        # data.write(str_df)
        sendmsg=''
        for i in df.index:
            #print (df.loc[i,'指数'])
            if df.loc[i,'指数'] in _bold_list:
                #print ('yes')
                sendmsg+='<tr align="center" bgcolor={0}><td><b>{1}</b></td><td><b><a href=\"{10}\" target=\"_blank\" style="color: black;">{2}<a></b></td><td><b>{3}</b></td><td ><b>{4}</b></td><td><b>{5}</b></td><td><b>{6}</b></td><td><b>{7}</b></td><td><b>{8}</b></td><td><b>{9}</b></td></tr>'.format(get_growth_color(df.loc[i,'估值']),i+1,df.loc[i,'指数'],df.loc[i,'PE'],df.loc[i,'PB'],df.loc[i,'PE百分位'],df.loc[i,'PB百分位'],df.loc[i,'ROE'],df.loc[i,'股息率'],df.loc[i,'估值'],df.loc[i,'链接'])
            else:
                #print ('no')
                sendmsg+='<tr align="center" bgcolor={0}><td>{1}</td><td><a href=\"{10}\" target=\"_blank\" style="color: black;">{2}<a></td><td>{3}</td><td >{4}</td><td>{5}</td><td>{6}</td><td>{7}</td><td>{8}</td><td>{9}</td></tr>'.format(get_growth_color(df.loc[i,'估值']),i+1,df.loc[i,'指数'],df.loc[i,'PE'],df.loc[i,'PB'],df.loc[i,'PE百分位'],df.loc[i,'PB百分位'],df.loc[i,'ROE'],df.loc[i,'股息率'],df.loc[i,'估值'],df.loc[i,'链接'])
        html_str=Template(table_head).safe_substitute({'CONTENT':sendmsg})
        #print (html_str)
        data.write(html_str)
    #return html_str

    data.write('</html>')
    data.close()


def pushplus(topic='me'):
    send_message(key=topic,_itype='file',_str="fund.html",_title='基金估值({})'.format(time.strftime('%m-%d', time.localtime(time.time()))),_template='html')
    print ('Sent by pushplus!')

@timer_decorator
def main(topic='me'):
    print ('Start topic: {}'.format(topic))
    if is_use_proxy:
        use_proxy()
    df=get_fund_data()
    create_html(df=df)
    pushplus(topic=topic)
    print ('{0}: Completed!'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))))

if __name__ == '__main__':
    if len(sys.argv) == 1:
        main('me')
        #test()
    else:
        para_argv=sys.argv[1][1:]
        main(para_argv)