import sys 
sys.path.append("..") 
from cloud import *
from cloud.utils.lib import *

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

def login():
    client = TTRClient(ttrss_url, ttrss_username, ttrss_password, auto_login=True)
    client.login()
    return client

def get_feeds(client):
    #feeds=client.get_feeds(cat_id=8,unread_only=True)
    _ID= 4 if is_vps else 8
    feeds=client.get_feeds(cat_id=_ID)
    return feeds



def get_css_sp(cssfile='./table_sp.css'):
    with open(cssfile,  'r', encoding='utf-8') as src:
        content = src.read()
    return content

def get_data(city):
    is_filter_date=1
    def getYesterday(): 
        today=datetime.now().date()
        oneday=timedelta(days=1) 
        yesterday=today-oneday  
        return yesterday
    yesterday_date=getYesterday().strftime("%Y-%m-%d")
    today_date=datetime.now().date().strftime("%Y-%m-%d")
    interested_days=[yesterday_date,today_date]
    #print (today_date,yesterday_date)
    '''
    def filter_date_by_date(update_date):
    
        if update_date in interested_days:
            return 1
        else:
            return 0
    '''
    def filter_date(paper):
        _today=datetime.now()
        _dtime=paper['datetime']
        diff=_today-_dtime
        #print (_dtime,diff)
        if diff < timedelta(hours=25): 
            return 1
        else:
            return 0
        pass

    def is_date_after_today(paper):
        _today=datetime.now()
        diff=paper-_today
        if diff > timedelta(days=-1): 
            return 1
        else:
            return 0
        pass
        
    def extract_date(text):
        pattern = r'\d{4}[.]\d{2}[.]\d{2}'
        match = re.search(pattern, text)
        if match:
            return match.group()
        else:
            return None

    def parse_date(text):
        formats = ['%Y-%m-%d', '%m/%d/%Y', '%d-%b-%Y','%Y.%m.%d']
        for fmt in formats:
            try:
                date_obj = datetime.strptime(text, fmt)
                return date_obj.strftime('%Y-%m-%d')
            except ValueError:
                pass
        return None
        

    
    interests=["大麦网"+str(city)]
    print (interests)
    #interests=['大麦网成都','大麦网西安']
    client=login()
    feeds=get_feeds(client)
    #print (feeds)
    feed_list=[]
    for i in feeds:
        #print (i)
        if i.title not in interests:
            continue
        data_list=[]
        data_list_after=[]
        ino=1
        for j in i.headlines():
            if j.unread == False:
                continue  
            z=j.full_article()
            data={}
            #print (z.link,z.title,z.updated,z.comments,z.author,z.id,z.content,extract_date(z.content))
            #print (j.title,j.excerpt,j.link,j.updated,j.tags,j.published,j.labels)
            if extract_date(z.content):
                _idate=extract_date(z.content)
                data['updated']=extract_date(z.content)
                date_object = datetime.strptime(extract_date(z.content), "%Y.%m.%d").strftime("%Y-%m-%d")
            else:
                date_object = ""
                data['updated']=""
            #print (date_object)

            data['id']=ino
            data['title']=j.title.replace(" 网页链接","")
            data['title']=data['title'].replace(i.title+'：',"",1)
            data['link']=j.link
            data['datetime']=j.full_article().updated            
            data['date']=date_object
            data['content']=j.full_article().content

      
                #print (data['title'],data['date'],is_date_after_today(datetime.strptime(date_object, "%Y-%m-%d")))
            #
            if is_filter_date and not filter_date(data):
                if is_filter_date and date_object and is_date_after_today(datetime.strptime(date_object, "%Y-%m-%d")):
                    data_list_after.append(data)
                #continue
            else:
                if date_object and is_date_after_today(datetime.strptime(date_object, "%Y-%m-%d")):
                    data_list.append(data)
            
            ino+=1
        data_list=sorted(data_list, key = lambda i: i['date'],reverse=False)
        data_list_after=sorted(data_list_after, key = lambda i: i['date'],reverse=False)  
        df_today=pd.DataFrame(data_list)
        df_recent=pd.DataFrame(data_list_after)
        
        if len(data_list) > 0:
            #feed_list.append({"key":"今日更新","data":df_today,'headline_count':len(data_list)})
            feed_list.append({"key":"今日更新","data":data_list,'headline_count':len(data_list),"df":df_today})
        #feed_list.append({"key":"近期演出","data":df_recent,'headline_count':len(data_list_after)})
        feed_list.append({"key":"近期演出","data":data_list_after,'headline_count':len(data_list_after),"df":df_recent})

    #print (df_today)
    #print (df_recent)
    nfeed=0
    nheadline=0
    for i in feed_list:
        if len(i['data']) >0 :
            nfeed+=1
            nheadline+=i['headline_count']
    #print (nfeed,nheadline)
    return feed_list

def generate_md(feed_list,city):
    nuOfHtml=1
    def create_table_header():
        _header="\n| 编号  | 演出  | 日期 |\n|----------------------------------|-------------------------------|---------------------------------|\n"
        return _header
    
    def create_md(nuOfHtml):
        htmlName=f'damai_{nuOfHtml}.md'
        fin=open(htmlName,'w',encoding = 'utf-8')
        msg=get_css_sp()
        return fin, msg
    date, times = get_time()
    f,sendmsg=create_md(nuOfHtml)
    nfeed=0
    for i in feed_list:
        if len(i['data']) >0 :
            nfeed+=1
    if  nfeed <= 0:
        f.write('<font size="3">🕔今天是{}，无信息更新。</font></br>'.format(date))
    else:
        sendmsg+='##### 🕔更新时间: {0} <br> \n'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        sendmsg+='##### 🎟️信息来源: 大麦网<font color=\"indianred\">{}</font><br> \n\n\n'.format(city)
        for  idata in feed_list:
            print (idata['key'])
            #print (idata)
            ino=1
            #print (idata)
            if idata['headline_count'] > 0:
                #print ('hello')
                sendmsg+="⏺ <font color=\"indianred\">{0}</font>: 共 {1} 场</br> \n \n \n".format(idata['key'],idata['headline_count'])
                #sendmsg+=tableHtml
                #ikey+=1
                if idata['key'] == "今日更新":
                    pass
                    sendmsg+=create_table_header()
                    df= idata['df']
                    df = df.drop(['id','datetime','date','content'], axis=1)
                    df['title'] = df['title'].apply(lambda x: x.replace("|", "\Vert"))
                    #sendmsg+=df.to_markdown()
                    
                    #print (df)
                    for row in  df.index:
                        sendmsg+='|{0}|{3}|[{1}]({2})|\n'.format(str(row+1),df.loc[row]['title'],df.loc[row]['link'],df.loc[row]['updated'])
                        
                        
                        #print (df.loc[row]['title'])
                        #print (df.index,df.columns)
                        pass
                        #sendmsg+=df.loc[row]['title']
                        #sendmsg+=df.loc[row]['link']
                        #sendmsg+=df.loc[row]['date']
                    # for ii, data in  enumerate(idata["data"]):
                    #     #print (ii)
                    #     _toBeAddStr = "<tr><td align=center>{0}</td><td><a href=\"{1}\"target=\"_blank\"><font color=\"blue\">{2}</font></a></td><td align=center>{3}</td></tr>".format(ii+1,data['link'],data['title'],data['date'])
                    #     #print (ii,len(sendmsg),len(_toBeAddStr),'\n')
                    #     if len(sendmsg)+len(_toBeAddStr) < 19900:   #19900
                    #         sendmsg += _toBeAddStr
                    #     else:
                    #         #print (sendmsg)
                    #         f.write(sendmsg)
                    #         f.write('</table></html>')
                    #         f.close()
                    #         nuOfHtml+=1
                    #         f,sendmsg=create_html(nuOfHtml)
                    #         sendmsg +=tableHtml
                    #         sendmsg+=_toBeAddStr
                    #     ino+=1
                    # sendmsg+='</table></br>'
                else:
                    pass
            else:
                continue
        

    f.write(sendmsg)
    f.close()




def generate_html(feed_list,city): 
    nuOfHtml=1
    def create_html(nuOfHtml):
        htmlName=f'damai_{nuOfHtml}.html'
        fin=open(htmlName,'w',encoding = 'utf-8')
        headHtml="<html><head><style>table th {font-weight: bold; text-align: center !important; background: rgba(158,188,226,0.2); white-space: wrap;}table tbody tr:nth-child(2n) { background-color: #f2f2f2;}table{font-family: Arial, sans-serif; font-size: 12px;}</style><meta charset=\"utf-8\"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing=\"5\"}td,th{border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head>"
        #headHtml="<html><head><style>table{font-family: Arial, sans-serif; font-size: 12px;}</style><meta charset=\"utf-8\"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing=\"5\"}td,th{border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head>"
        return fin, headHtml
    date, times = get_time()
    tableHtml="<table><tr align=center><th style=\"min-width:30px\">序</th><th style=\"max-width:180px\">演出项目</th><th style=\"min-width:80px\">演出日期</th></tr>"
    #sendmsg ='推送时间:' + date+' '+times
    ino=1
    f,sendmsg=create_html(nuOfHtml)
    #f=open("./stock.html",'w',encoding = 'utf-8')
    nfeed=0
    nheadline=0
    stock_str_list=""
    icount=0
    
    for i in feed_list:
        if len(i['data']) >0 :
            nfeed+=1
            nheadline+=i['headline_count']
            stock_str_list+=i['key']            
            if icount < len(feed_list)-1:
                stock_str_list+=", "
                icount+=1
    

    
    if  nfeed <= 0:  
        #f.write("今天是{}，无信息更新。".format(date))         
        f.write('<font size="3">🕔今天是{}，无信息更新。</font></br>'.format(date))
    else:
        #f.write('<html><head><meta charset=\"utf-8\"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing=\"10\"}td,th{border:1px solid rgb(190,190,190);padding:1px 2px;text-align:left;line-height:1.3em;}</style></head>')
        #f.write("<html><head><style>table{font-family: Arial, sans-serif; font-size: 12px;}</style><meta charset=\"utf-8\"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing=\"5\"}td,th{border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head>")

        sendmsg+='🕔更新时间: {0} </br>'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        sendmsg+='🎟️信息来源: 大麦网<font color=\"indianred\">{}</font></br>'.format(city)
        #f.write("今天是 {} ，共<font color=\"red\"> {} </font>支股票、 <font color=\"red\"> {} </font>篇公告更新。股票是 <font color=\"red\">{}</font></tr>  。</br></br>".format(date,nfeed, nheadline,stock_str_list))
        ikey=1
        for  idata in feed_list:
            print (idata['key'])
            #print (idata)
            ino=1
            #print (idata)
            if idata['headline_count'] > 0:
                #print ('hello')
                sendmsg+="⏺ <font color=\"indianred\">{0}</font>: 共 {1} 场</br>".format(idata['key'],idata['headline_count'])
                sendmsg+=tableHtml
                ikey+=1
                if idata['key'] == "今日更新":
                    for ii, data in  enumerate(idata["data"]):
                        #print (ii)
                        _toBeAddStr = "<tr><td align=center>{0}</td><td><a href=\"{1}\"target=\"_blank\"><font color=\"blue\">{2}</font></a></td><td align=center>{3}</td></tr>".format(ii+1,data['link'],data['title'],data['date'])
                        #print (ii,len(sendmsg),len(_toBeAddStr),'\n')
                        if len(sendmsg)+len(_toBeAddStr) < 19900:   #19900
                            sendmsg += _toBeAddStr
                        else:
                            #print (sendmsg)
                            f.write(sendmsg)
                            f.write('</table></html>')
                            f.close()
                            nuOfHtml+=1
                            f,sendmsg=create_html(nuOfHtml)
                            sendmsg +=tableHtml
                            sendmsg+=_toBeAddStr
                        ino+=1
                    sendmsg+='</table></br>'
                else:
                    #sendmsg+="✅ <font color=\"green\">{0}</font> {1} 场</br>".format(idata['key'],idata['headline_count'])
                    #sendmsg+=tableHtml
                    for ii, data in  enumerate(idata["data"]):
                        #print (ii)
                        _toBeAddStr = "<tr><td align=center>{0}</td><td><a href=\"{1}\" target=\"_blank\"><font color=\"black\">{2}</font></a></td><td align=center>{3}</td></tr>".format(ii+1,data['link'],data['title'],data['date'])
                        #print (ii,len(sendmsg),len(_toBeAddStr),'\n')
                        if len(sendmsg)+len(_toBeAddStr) < 19900:   #19900
                            sendmsg += _toBeAddStr
                        else:
                            #print (sendmsg)
                            f.write(sendmsg)
                            f.write('</table></html>')
                            f.close()
                            nuOfHtml+=1
                            f,sendmsg=create_html(nuOfHtml)
                            sendmsg +=tableHtml
                            sendmsg+=_toBeAddStr
                        ino+=1
                    sendmsg+='</table></br>'
            else:
                continue
            #html_str=Template(tableHtml).safe_substitute({'CONTENT':sendmsg})
            #f.write(sendmsg+'</table>'#)

        ################################ 
        f.write(sendmsg)
        f.write('</html>')
        f.close()
    return nuOfHtml

def pushplus(topic='me',_city='成都',_nuOfHtml=1,): 
    print ('Pushing html by pushplus to Wechat ... ')
    for i in range(1,_nuOfHtml+1):
        fileName=f'damai_{i}.html'
        if os.path.exists(fileName):   
            pageInfo = '' if _nuOfHtml < 2 else f' [{i}/{_nuOfHtml}]'
            response=send_message(key=topic,_itype='file',_str=fileName,_title='{}演出{}'.format(_city,time.strftime('%m-%d', time.localtime(time.time())))+pageInfo,_template='html',_send_type='post')
            #send_work_weixin(_itype='file',_str=fileName,_title='光学文献{}'.format(time.strftime('%m-%d', time.localtime(time.time())))+pageInfo)
            #_title='{}演出({})'.format(city,time.strftime('%m-%d', time.localtime(time.time())))
            time.sleep(1)

        else:
            pass
    print ('Sent by pushplus!')

def only_send(topic='me'):
    send_message(key=topic,_itype='file',_str="./damai_1.html",_title='test({})'.format(time.strftime('%Y-%m-%d', time.localtime(time.time()))),_template='html',_send_type='post')
    print ('Sent by pushplus!') 



def main(topic,city):
    print ('topic: {}'.format(topic))
    today_info=get_data(city)
    #nuOfHtml=generate_md(today_info,city)
    nuOfHtml=generate_html(today_info,city)
    #only_send()
    pushplus(topic,city,nuOfHtml)


if __name__ == '__main__':
    if len(sys.argv) == 1:
        main('me','成都')
        #main('me','西安')
        #test()
    else:
        para_argv=sys.argv[1][1:]
        city=sys.argv[2][1:]
        main(para_argv,city)