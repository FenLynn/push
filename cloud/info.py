from .config import *
from .utils.lib import *
from .net import *
from .tool import *
from .image import *



def get_game_schedule(games=[]):
    def drop_duplicate_rows(customers: pd.DataFrame) -> pd.DataFrame:
        customers.drop_duplicates(subset='content', keep='first', inplace=True)
        return customers

    class daq_server():
        def __init__(self,key_list):
            self.key_list=key_list     
            pass
    
        
        def get_all_game_info(self):
            df=pd.DataFrame()
            df_list=[]
            for igame in self.key_list:
                df_list.append(self.get_game_info(igame))
            df=pd.concat(df_list)
            if not df.empty:
                df=df.sort_values(by=['date','time'],ascending=True)
                df=df.reset_index(drop=True)        
            return df
        
        def get_today_game_info(self):
            today=datetime.today().strftime('%Y-%m-%d')
            #today='2022-12-13'
            df=self.get_all_game_info()
            if not df.empty:
                df_today=df[df['date']==today]
                if not df_today.empty:
                    df_today=df_today.sort_values(by='time',ascending=True)    
                    df_today=df_today.reset_index(drop=True)
                return df_today
            else:
                return df
        
        def get_game_info(self,key_str):
            def get_date(sdate=''):
                date_str_regrex=re.compile(r'<h2 title=\"\d{4}[-/]?\d{2}[-/]?\d{2}\">')
                pos=re.search(r'<h2 title=\"\d{4}[-/]?\d{2}[-/]?\d{2}\">',sdate)
                date_str=date_str_regrex.findall(sdate)
                if len(date_str) == 0 :
                    return '',0
                else:
                    _date= pattern_date.findall(date_str[0])[0]
                    return _date,pos.start()
            
            #url = 'https://www.zhibo8.cc'
            url = 'https://www.zhibo8.com'
            res = requests.get(url)
            mylog.debug(key_str+' get requests ok!')
            res.encoding = 'utf-8'
            resTxt = res.text
            # with open('./server.html','r',encoding='utf-8') as f:
            #     resTxt=f.read()
            # f.close()
            rows=[]
            pattern_date = re.compile('\d{4}[-/]?\d{2}[-/]?\d{2}')
            pattern_time = re.compile('\d{1,2}:\d{1,2}')
            idx=0
            #date_list=[]
            last_date,pos_date=get_date(resTxt)
            
            while idx != -1:
                next_date,pos_date=get_date(resTxt)
                t=re.search(r'<li label=\"(.*?)\">',resTxt)
                #print (date_list)
                idx=t.start()
                idy=t.end()
                
                if idx < pos_date:
                    current_date=last_date
                else:
                    current_date=next_date
                    last_date=next_date
                
                
                match_wzry=resTxt[idx:idy]
                resTxt = resTxt[idx:]
                idz = resTxt.find('</li>')
                match = resTxt[:idz]
        
                if match_wzry.find(key_str) != -1:
                    #print (match_wzry)
                    time_match_in_html=re.compile(r'">\d{1,2}:\d{1,2} <b>')
                    time_str=time_match_in_html.findall(match)[0]
                    matchTime=pattern_time.findall(time_str)[0]
                    phase_home = match[match.find('<b>') + len('<b>') : match.find('<img src=')]
                    m_idx = match.find('</b>')
                    m_sidx= match.find('" > ')
                    tmp = match[m_sidx+len('" > '):m_idx]
                    m_idx = tmp.rfind('>')
                    visiting = tmp[m_idx+1:]
                    m_idx = match.find('"_blank">')
                    media = match[m_idx + len('"_blank">'): match.find('</a>')]
                    matchInfo = phase_home + 'VS'+ visiting 
                    _time = pattern_time.findall(matchTime)[0]
                    temp_dict={'date':current_date,'time':_time,'type':key_str,'content':matchInfo,'media':media}
                    rows.append(temp_dict)
                
                resTxt = resTxt[idz:]
                next_search_start= re.search(r'<li label=\"(.*?)\">',resTxt)
                if next_search_start is None:
                    break
                else:            
                    idx =next_search_start.start()
            game_df=pd.DataFrame(rows)
            return game_df
        

    class daq_local():
        def __init__(self,key_list):
            self.key_list=key_list
            url = 'http://www.zhibo8.com'
            #res = requests.get(url)
            res = safe_request(url,  timeout=5)
            res.encoding = 'utf-8'
            self.resTxt = res.text
            with open('./game.txt','w',encoding='utf-8') as f:
                f.write(self.resTxt)
            f.close()
            
            pass
    
        def get_football_world_cup(self):
            #url = 'http://www.zhibo8.cc'
            url = 'https://www.zhibo8.com'
            res = requests.get(url)
            res.encoding = 'utf-8'
            resTxt = res.text
            idx = resTxt.find('<li label="世界杯,')
            rows=[]
            pattern_date = re.compile('\d{4}[-/]?\d{2}[-/]?\d{2}')
            pattern_time = re.compile('\d{1,2}:\d{1,2}')
            while idx != -1:
                resTxt = resTxt[idx:]
                idx = resTxt.find('</li>')
                match = resTxt[:idx]
                if match.find('鏖战世界波') == -1:
                    m_idx = match.find('data-time="')
                    matchTime = match[m_idx + len('data-time="'): match.find('">')]
                    m_idx = match.find('<b>')
                    phase_home = match[m_idx + len('<b>') : match.find('<img src=')]
                    m_idx = match.find('</b>')
                    tmp = match[:m_idx]
                    m_idx = tmp.rfind('>')
                    # print(m_idx)
                    visiting = tmp[m_idx+1:]
                    m_idx = match.find('"_blank">')
                    media = match[m_idx + len('"_blank">'): match.find('</a>')]
                    matchInfo = phase_home + 'VS'+ visiting         
                    _date = pattern_date.findall(matchTime)[0]
                    _time = pattern_time.findall(matchTime)[0]
                    temp_dict={'date':_date,'time':_time,'type':'世界杯','content':matchInfo,'media':media}
                    rows.append(temp_dict)
                resTxt = resTxt[idx:]
                idx = resTxt.find('<li label="世界杯,')
            game_df=pd.DataFrame(rows)
            return game_df
        
        def get_game_info(self,key_str):
            resTxt=self.resTxt
            rows=[]
            pattern_date = re.compile('\d{4}[-/]?\d{2}[-/]?\d{2}')
            pattern_time = re.compile('\d{1,2}:\d{1,2}')
            idx=0
            while idx != -1:
                t=re.search(r'<li label=\"(.*?)\" id=',resTxt)           
                idx=t.start()
                idy=t.end()
                match_wzry=resTxt[idx:idy]
                resTxt = resTxt[idx:]
                idz = resTxt.find('</li>')
                match = resTxt[:idz]
                if match_wzry.find(key_str) != -1:
                    m_idx = match.find('data-time="')
                    matchTime = match[m_idx + len('data-time="'): match.find('">')]
                    m_idx = match.find('<b>')
                    phase_home = match[m_idx + len('<b>') : match.find('<img src=')]
                    m_idx = match.find('</b>')
                    tmp = match[:m_idx]
                    m_idx_start = tmp.rfind('/>')
                    m_idx = tmp.rfind('</span>')
                    visiting = tmp[m_idx_start+1:m_idx]
                    m_idx = match.find('"_blank">')
                    media = match[m_idx + len('"_blank">'): match.find('</a>')]
                    matchInfo = phase_home + 'VS'+ visiting         
                    #print (matchInfo)
                    _date = pattern_date.findall(matchTime)[0]
                    _time = pattern_time.findall(matchTime)[0]
                    
                    temp_dict={'date':_date,'time':_time,'type':key_str,'content':matchInfo,'media':media}
                    temp_dict['content']=temp_dict['content'].replace(" ","")
                    
                    temp_dict['content']=temp_dict['content'].replace('\n<spanclass="_league">','')
                    temp_dict['content']=temp_dict['content'].replace('</span>\n<spanclass="_teams">\n',' ')
                    temp_dict['content']=temp_dict['content'].replace(">\n"," ")
                    temp_dict['content']=temp_dict['content'].replace("VS"," vs.")
                    #print (temp_dict)
                    rows.append(temp_dict)
                    #print (rows)
            
                resTxt = resTxt[idz:]
                next_search_start= re.search(r'<li label=\"(.*?)\" id=',resTxt)
                if next_search_start is None:
                    break
                else:            
                    idx =next_search_start.start()
            game_df=pd.DataFrame(rows)
            return game_df
        
        def get_today_game_info(self):
            today=datetime.today().strftime('%Y-%m-%d')
            #today='2022-12-13'
            df=self.get_all_game_info()
            if not df.empty:
                df_today=df[df['date']==today]
                if not df_today.empty:
                    df_today=df_today.sort_values(by=['date','time'],ascending=True)    
                    df_today=df_today.reset_index(drop=True)
                return df_today
            else:
                return df
        
        def get_today_tomorrow_game_info(self):
            mylog.debug('start game today tomorrow  info ')
            today=datetime.today().strftime('%Y-%m-%d')
            tomorrow_dt=datetime.now()+timedelta(days=1)
            tomorrow=tomorrow_dt.strftime('%Y-%m-%d')
            #print (today,tomorrow)
            #today='2022-12-13'
            
            df=self.get_all_game_info()
            mylog.debug('end game all info ')
            if not df.empty:
                #print (df)
                df_today=df[(df['date']==today) | (df['date']==tomorrow)]
                if not df_today.empty:
                    df_today=df_today.sort_values(by=['date','time'],ascending=True)    
                    df_today=df_today.reset_index(drop=True)
                    #print (type(df_today.iloc[0,1]))
                    #index_names = df_today[ df_today['time'] == 21 ].index
                    #index_names = df[ (df['Age'] >= 21) & (df['University'] == 'BHU')].index
                    #if df['date']==tomorrow:
                    #df_today[df_today['date']==tomorrow]
                    for index, row in df_today.iterrows():
                        
                        if row["date"]==tomorrow:
                            row["time"]='明天 '+row["time"]
                        #print (row["date"]==tomorrow, row["time"])
                    
                    
                    #df_today['time']= df['plus'].map(lambda x: str(x)[7:])
                    #d#f_today.loc[(df_today.date == tomorrow) ,'time'] = '明天 '+df['time']
                        #df['time']=df['time']+'明天'
                    
                    
                return df_today
            else:
                return df   
        
        def get_all_game_info(self):
            mylog.debug('enter all game info')
            df=pd.DataFrame()
            df_list=[]
            mylog.debug(' '.join(self.key_list))
            for igame in self.key_list:
                if igame == '世界杯':
                    mylog.debug('start  世界杯 ')
                    df_list.append(self.get_football_world_cup())
                else:
                    mylog.debug('start  {0} '.format(igame))
                    df_list.append(self.get_game_info(igame))
            df=pd.concat(df_list)
            if not df.empty:
                df=df.sort_values(by=['date','time'],ascending=True)
                df=df.reset_index(drop=True)
            df=drop_duplicate_rows(df)
            #print (df)
            return df

    if is_server():
        mylog.debug('server')
        #a=daq_server(games)
        a=daq_local(games) 
        return a
    else:
        mylog.debug('local')
        a=daq_local(games) 
        return a


def get_oil_price():     
    def gen_df(price):
        df_list=[]
        df_name=[]
        for key,value in price.items():
            _df=pd.DataFrame(value)
            _df=_df.set_index(keys='date')
            df_list.append(_df)
            df_name.append(key)
        combined_df=pd.concat(df_list,axis=1)    
        combined_df.columns  =  df_name
        combined_df = combined_df.reset_index()   # 将date恢复为普通列
        return combined_df

    url='https://v2.xxapi.cn/api/oilPrice'
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"}
    price={'四川':{'date':[],'price':[]},'陕西':{'date':[],'price':[]},'湖北':{'date':[],'price':[]},'北京':{'date':[],'price':[]}}
    try:
        #response = safe_request.get(url, headers=headers)
        response = safe_request(url,  timeout=5 ,headers=headers)
        data=response.json()
        if data['code'] == 200:
            for i in data['data']:
                _name=i['regionName'].replace('省','').replace('市','')
                if _name in price.keys():
                    price[_name]['date'].append(i['date'])
                    price[_name]['price'].append(i['n95'])
                else:
                    pass
            return gen_df(price)
        else:
            print ('error!')
            return pd.DataFrame()
    except:
        print ('error!')
        return pd.DataFrame()

def get_game(games=[]):
    game=get_game_schedule(games)
    today_game=game.get_today_tomorrow_game_info()
    return today_game


def get_hot_search(pic_path='./hot_search.jpg'):
    if is_vps:
        web=['weibo','douyin']
    else:
        web=['bilibili','weibo','douyin','zhihu','36kr','baidu','sspai','ithome','thepaper','toutiao','tieba','juejin','newsqq']
    tempStr=''
    for i in web:
        mylog.debug(i)
        url='https://api.zxz.ee/api/hot/?type={}'.format(i)
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
            }
            #response = requests.get(url, headers=headers)
            response = safe_request(url, headers=headers)
            data=response.json()
            if data['code'] == 200:
                for j in data['data']:
                    tempStr+=j['title']
                    tempStr+=' '
        except json.decoder.JSONDecodeError or requests.exceptions.JSONDecodeError:
            print ('{} error data fetch'.format(tag=sys._getframe().f_code.co_name[4:]))    
    tempStr=filter_wordcloud_stopword(tempStr,stopword)
    get_wordcloud(tempStr,pic_path)
    pic_url=upload_image_to_cdn(pic_path)   
    return pic_url