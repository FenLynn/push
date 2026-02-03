import sys 
sys.path.append("..") 
from cloud import *
from cloud.utils.lib import *

################# keywords
chn_keywords=["光纤","激光","高功率","窄线宽","受激拉曼散射","模式不稳定","受激布里渊散射","同带泵浦","合束器","机器学习","神经网络","深度学习","自旋","轨道"]
eng_keywords=["fiber","laser","narrow linewidth","tandem","coherrent","transverse mode instability","stimulated Raman scattering","stimulated Brillouin scattering","SRS","SBS","TMI","1018 nm","combiner","machine learning","neural network","deep learning","orbital angular momentum","skyrmions","metafiber","multimode"]

################# journal
general_journals=["Scientific Reports","物理学报","Micromachines","Nature Communications","IEEE Journal of Quantum Electronics"]
MDPIJournals=['Micromachines','Photonics']
OSAJournal=['Optica','Optical Materials Express','Optics Continuum','Optics Express','Optics Letters','Photonics Research','Journal of Lightwave Technology','Journal of the Optical Society of America B','Applied Optics','Advances in Optics and Photonics']

################# time
count_days = 2
remain_days = 4
past_hours=25  #25

################
def get_osa_past_hours():
    now = datetime.now()
    zeroToday = now - timedelta(hours=now.hour, minutes=now.minute, seconds=now.second, microseconds=now.microsecond)      # 获取今天零点      # 获取23:59:59
    osaToday = zeroToday + timedelta(hours=13, minutes=00, seconds=00)  #13
    _diff=(now-osaToday)
    total_hours = int(_diff.total_seconds() / 3600)+25
    return total_hours
    
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
    _ID= 2 if is_vps else 6
    feeds=client.get_feeds(cat_id=_ID,unread_only=True)
    return feeds

def include_keywords(paper):
    total_key_words=chn_keywords+eng_keywords
    def find_keywords(text, keywords):
        keyword_pattern = re.compile("|".join(keywords), re.IGNORECASE)
        matches = keyword_pattern.findall(text)
        return matches
    
    found_title_keywords=find_keywords(paper['title'],total_key_words)
    found_abstract_keywords=find_keywords(paper['content'],total_key_words)
    
    found_unique_keywords=list(set([i.lower() for i in (found_title_keywords+found_abstract_keywords)]))

    if len(found_title_keywords) == 0 and len(found_abstract_keywords)==0:
        return 0,found_unique_keywords
    else:
        return 1,found_unique_keywords

def get_data():
    is_filter_date=1
    is_mark_keyword=1
    def getYesterday(): 
        today=datetime.now().date()
        oneday=timedelta(days=1) 
        yesterday=today-oneday  
        return yesterday
    yesterday_date=getYesterday().strftime("%Y-%m-%d")
    today_date=datetime.now().date().strftime("%Y-%m-%d")
    interested_days=[yesterday_date,today_date]
    #print (today_date,yesterday_date)
    def filter_date_by_date(update_date):
        if update_date in interested_days:
            return 1
        else:
            return 0
    
    def filter_date(paper,journalTitle):
        _today=datetime.now()
        _dtime=paper['datetime']
        diff=_today-_dtime
        _past_hours = get_osa_past_hours() if journalTitle in OSAJournal else past_hours       
        #print (paper)
        if diff < timedelta(hours=_past_hours): 
            return 1
        else:
            return 0
        pass
  
    client=login()
    #feeds = client.get_feeds(cat_id=6)
    feeds=get_feeds(client)
    print ('\n存在未读文章的期刊: '+', '.join([i.title for i in feeds]))
    feed_list=[]   
    test_status=0
    for i in feeds:
        if test_status:
            #interests=["Advanced Imaging","Laser Physics","Optical Fiber Technology"]
            interests=["Advanced Imaging","Optical Fiber Technology"]
            if i.title not in interests:
                continue
            else:
                pass
        print (f'\n处理期刊 {i.title} 中...')
        data_list=[]
        ino=1
        num_key_counts=0
        for j in i.headlines():
            #####
            k=j.full_article().id
            
            #####
            if j.unread == False:
                continue
            else:
                #print (k)
                if not test_status:
                    client.toggle_unread([k])   #处理一次后变为已读
                pass
            paper={}
            paper['id']=ino
            paper['title']=j.title
            paper['title']=paper['title'].replace("【{0}】".format(i.title),'')
            if i.title in MDPIJournals:   
                pat = '^{}, Vol. [0-9]*, Pages [0-9]*: '.format(i.title)   
                matchResult = re.findall(pat,paper['title'])                
                if matchResult:
                    paper['title']=paper['title'].replace(matchResult[0],'')            
            paper['link']=j.link
            paper['datetime']=j.full_article().updated
            paper['updated']='{}/{}'.format(j.updated.date().month,j.updated.date().day)
            paper['date']=j.updated.date().strftime("%Y-%m-%d")
            paper['content']=j.full_article().content
            paper['author']=j.full_article().author
            if is_mark_keyword:
                paper['is_include_keyword'],paper['keywords']=include_keywords(paper)
                if  paper['is_include_keyword']:
                    num_key_counts+=1
            ino+=1
            if is_filter_date and not filter_date(paper,i.title) :               
                continue                 
            else:
                if i.title in general_journals and not paper['is_include_keyword']:
                    pass
                else:
                    data_list.append(paper)
            #k.refresh_status()
            #client.make_read([k])
            #client.toggle_unread([k])
            pass
        feed_list.append({"journal":i.title,"data":data_list,"articles_nu":len(data_list)})
        print (i.title,len(data_list))
    today_info={"journals":0,"today":datetime.now().date().strftime("%Y-%m-%d"),"articles_sum":0,"journals_title":[],"paper":feed_list}
    for i in feed_list:
        today_info["articles_sum"]+=i["articles_nu"]
        if i["articles_nu"] > 0:
            today_info["journals_title"].append(i["journal"])
            today_info["journals"]+=1
    #print (today_info)        
    return today_info
             
def generate_html(today_info):  
    nuOfHtml=1
    def create_html():
        htmlName=f'paper_{nuOfHtml}.html'
        fin=open(htmlName,'w',encoding = 'utf-8')
        headHtml="<html><head><style>table th {font-weight: bold; text-align: center !important; background: rgba(158,188,226,0.2); white-space: wrap;}table tbody tr:nth-child(2n) { background-color: #f2f2f2;}table{font-family: Arial, sans-serif; font-size: 12px;}</style><meta charset=\"utf-8\"><style>html{font-family:sans-serif;}table{border-collapse:collapse;cellspacing=\"5\"}td,th{border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}</style></head>"
        return fin, headHtml
    date, times = get_time()
    tableHtml='<table><tr  align=center><th style=\"min-width:25px\">序</th><th style=\"min-width:270px\">文章标题</th><th style=\"min-width:50px\">关键词</th></tr>${CONTENT}</table>'
    f,tempStrf=create_html()
    ino=1
    if  today_info["articles_sum"] <= 0:  
        tempStrf+='<font size="3"> 🕔今天{}, 无光学文章更新.</font>'.format(today_info["today"])
        f.write(tempStrf)
        f.close()
        return nuOfHtml
    else:
        #'🕔 更新时间:{0} \n'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        tempStrf+='🕔更新时间:{0} \n'.format(time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time())))
        tempStrf+='⏺ 共<font color=\"cadetblue\"><b>{}</b></font>本期刊, <font color=\"cadetblue\"><b>{}</b></font>篇文章更新.</font></br>'.format(today_info["journals"],today_info["articles_sum"])
        #tempStrf+='<font size="3">🕔今天<b>{}</b>,共<font color=\"blue\"><b>{}</b></font>本期刊,<font color=\"blue\"><b>{}</b></font>篇文章更新.</font></br>'.format(today_info["today"],today_info["journals"], today_info["articles_sum"])
        ijournal=1
        for idata in today_info["paper"]:
            if len(idata["data"]) > 0:
                sendmsg=" <font size=\"2\" color=\"cadetblue\"><b>{0}</b></font> <font size=\"2\" <b>  {1}</b>篇</font></br>".format(idata['journal'],str(idata['articles_nu']),ijournal)
                ijournal+=1
                for data in idata["data"]:
                    if data["is_include_keyword"]:
                        if len(",".join(data['keywords'])) > 9:
                            _align = 'left'
                        else:
                            _align ='center'
                        sendmsg += '<tr style="color: indianred;"><td align="center">{0}</td><td align="left"><a href=\"{1}\" target=\"_blank\"><font color=\"indianred\">{2}</font></a></td><td align={4}>{3}</td>'.format(ino,data['link'],data['title']," ".join(data['keywords']),_align)
                    else:
                        #sendmsg +='<tr><td align="center"><font color=\"gray\">{0}</font></td><td align="left"><a href=\"{1}\" target=\"_blank\"><font color=\"gray\">{2}</font></a> </td><td align="center"><font color=\"gray\">{3}</font></td>'.format(ino,data['link'],data['title'],"无")
                        sendmsg += '<tr style="color: gray;"><td align="center">{0}</td><td align="left"><a href=\"{1}\" target=\"_blank\"><font color=\"gray\">{2}</font></a></td><td align="center">{3}</td>'.format(ino,data['link'],data['title'],"无")
                    sendmsg += '</tr>'
                    ino+=1
            else:
                continue
            html_str=Template(tableHtml).safe_substitute({'CONTENT':sendmsg}) 
            _toBeAddStr=html_str+'</br>'
            if len(tempStrf) + len(_toBeAddStr) < 19900:
                tempStrf+=_toBeAddStr
            else:
                f.write(tempStrf)
                f.write('</html>')
                f.close()
                nuOfHtml+=1
                f,tempStrf=create_html()
                tempStrf+=_toBeAddStr
                pass
        f.write(tempStrf)
        f.write('</html>')
        f.close()
        return nuOfHtml

def archive_paper(today_info,_nuOfHtml):
    for i in range(1,_nuOfHtml+1):
        fileName=f'paper_{i}.html'
        pageInfo = '' if _nuOfHtml < 2 else f'_{i}'
        s_file='./archive/{}{}.html'.format(today_info['today'],pageInfo)
        os.system('cp -rf {0} {1}'.format(fileName, s_file))       

def pushplus(topic='me',_nuOfHtml=1): 
    print ('Pushing html by pushplus to Wechat ... ')
    for i in range(1,_nuOfHtml+1):
        fileName=f'paper_{i}.html'
        if os.path.exists(fileName):   
            pageInfo = '' if _nuOfHtml < 2 else f' [{i}/{_nuOfHtml}]'
            response=send_message(key=topic,_itype='file',_str=fileName,_title='光学文献{}'.format(time.strftime('%m-%d', time.localtime(time.time())))+pageInfo,_template='html',_send_type='post')
            #send_work_weixin(_itype='file',_str=fileName,_title='光学文献{}'.format(time.strftime('%m-%d', time.localtime(time.time())))+pageInfo)
            time.sleep(10)
            
        else:
            pass
    print ('Sent by pushplus!')

def main(topic):           
    ############# topic #######################
    print ('topic: {}'.format(topic))

    ############### journals ###################
    today_info=get_data()
    #print (today_info)
    nuOfHtml=generate_html(today_info)
    
    ############# push #########################
    pushplus(topic,nuOfHtml)
    
    ############# test archive #################
    #today_info={}
    #today_info['today']='2024-12-22'   
    #archive_paper(today_info,3)
    archive_paper(today_info,nuOfHtml)
    ############# ending   #####################
    print('finished\n')  

def only_send(topic):
    response=send_message(key=topic,_itype='file',_str="./paper_1.html",_title='光学文献{}test'.format(time.strftime('%m-%d', time.localtime(time.time()))),_template='html',_send_type='post')
    
if __name__ == '__main__':
    if len(sys.argv) == 1:
       # main('me')
        only_send('me')
    else:
        para_argv=sys.argv[1][1:]
        main(para_argv)
        
