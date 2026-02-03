from .config import *
from .utils.lib import *

def get_host_ip():
    n=1
    while (n<10):
        try:
            req = requests.get('http://ifconfig.me/ip', timeout=10)
            ip=req.text.strip()
            return ip
        except requests.exceptions.ConnectionError:
            print('IPconfig.me  ConnectionError -- please wait 3 seconds')
            time.sleep(3) 
            n+=1
        except requests.exceptions.RequestException as e:
            print('IPconfig.me  RequestError -- please wait 3 seconds')
            time.sleep(3)
            n+=1    
#   if n>= 10:
#       return '192.168.12.21'
    
def is_server():
    if get_host_ip() in server_ip:
        return True
    else:
        return False
    
def general_proxy():
    if not is_server():
        return proxy_ip[0]
    else:
        return ''

def plot_wra_func(func):
    def wrapper(*args, **kwargs):
        try:
            res = func(*args, **kwargs)
            plt.close('all')
            if True:
            #if is_server():
                _lag=int(random.uniform(5,30))
                print (f'Info: 休息{ _lag} 秒中...')
                time.sleep(_lag)
            return res
        except:
            print ('Error!')
            return None       
    return wrapper   

def plot_wra_func_old(func):
    def wrapper(*args, **kwargs):
        res = func(*args, **kwargs)
        plt.close('all')
        if True:
        #if is_server():
            _lag=random.uniform(5,30)
            print (f'Info: 休息{ _lag} 秒中...')
            time.sleep(_lag)
        return res
    return wrapper  


############# pushplus  #####################
def send_message(key='me',_itype='str',_str='content',_title='title',_template='html',_send_type='post'):
    token_list=p_token
    if _itype=='file':
        html_file=open(_str,"r",encoding = 'utf-8')
        msg=html_file.read()
    elif _itype=='str':
        msg=_str
    else:
        print ("type error")
        return
    for token in token_list:
        title = _title
        content = msg
        template = _template
        if _send_type == 'get':
            if key == 'baobao':
                url = "https://www.pushplus.plus/send?token={}&title={}&content={}&template={}&topic=12".format(token,title,content,template)
            elif key == 'me':
                url = "https://www.pushplus.plus/send?token={}&title={}&content={}&template={}".format(token,title,content,template)
            elif key == 'family':
                url = "https://www.pushplus.plus/send?token={}&title={}&content={}&template={}&topic=13".format(token,title,content,template)
            elif key == 'stock':
                url = "https://www.pushplus.plus/send?token={}&title={}&content={}&template={}&topic=14".format(token,title,content,template)
            elif key == 'paper':
                url = "https://www.pushplus.plus/send?token={}&title={}&content={}&template={}&topic=15".format(token,title,content,template)
            else:
                pass
            r = requests.get(url=url)
        elif _send_type== 'post':
            url = 'http://www.pushplus.plus/send'
            data={
                "token":token,
                "title":title,
                "content":content,
                "template":template
            }            
            if key == 'baobao':
                data.update({'topic':12})
            elif key == 'family':
                data.update({'topic':13})
            elif key == 'stock':
                data.update({'topic':14})
            elif key == 'paper':
                data.update({'topic':15})
            else:
                pass
            headers={'Content-type': 'application/json'}
            body=json.dumps(data).encode(encoding='utf-8')
            try:
                requests.post(url,data=body,headers=headers)
            except requests.exceptions.RequestException as e:
                print('Error: pushplus通知失败')
                raise SystemExit(e)
            
        print ('只发送自己!' if key == 'me'  else '发送到{0}群组!'.format(key))

        
def send_work_weixin(_itype='str',_str='content',_title='title',_template='html'):
    token=p_token[0]
    if _itype=='file':
        html_file=open(_str,"r",encoding = 'utf-8')
        msg=html_file.read()
    elif _itype=='str':
        msg=_str
    else:
        print ("type error")
        return
    
    title = _title
    content = msg


    url = 'http://www.pushplus.plus/send'
    data={
        "token":token,
        "title":title,
        "template":_template,
        "content":content,
        "channel":"cp",
        "webhook":"12"
    }            
    headers={'Content-type': 'application/json'}
    body=json.dumps(data).encode(encoding='utf-8')
    try:
        requests.post(url,data=body,headers=headers)
    except requests.exceptions.RequestException as e:
        print('Error: 企业微信pushplus通知失败')
        raise SystemExit(e)

        
        
def send_robot_text(_itype='str',_str='content',_template='text',mentioned_list=None, mentioned_mobile_list=None):
    #def send_text(, content, ):
    webhook= p_webhook
    header = {
                "Content-Type": "application/json",
                "Charset": "UTF-8"
                }
    if _itype=='file':
        html_file=open(_str,"r",encoding = 'utf-8')
        msg=html_file.read()
    elif _itype=='str':
        msg=_str
    else:
        print ("type error")
        return
    
    if _template=='text':
        data ={
            "msgtype": 'text',
            "text": {
                "content": msg
                ,"mentioned_list":mentioned_list
                ,"mentioned_mobile_list":mentioned_mobile_list
            }
        }
    elif _template=='markdown':
        data ={
            "msgtype":'markdown',
            "markdown": {
                "content": msg
            }
        }
    else:
        print ("template error!")
        return 
    
    data = json.dumps(data)
    info = requests.post(url=webhook, data=data, headers=header)


def send_robot_file(file=''):
    webhook = p_webhook
    # 获取media_id
    key = webhook.split('key=')[1]
    id_url = f'https://qyapi.weixin.qq.com/cgi-bin/webhook/upload_media?key={key}&type=file'
    files = {'file': open(file, 'rb')}
    res = requests.post(url=id_url, files=files)
    media_id = res.json()['media_id']
    header = {
                "Content-Type": "application/json",
                "Charset": "UTF-8"
                }
    data ={
    "msgtype": "file",
    "file": {
                "media_id": media_id
        }
    }
    data = json.dumps(data)
    info = requests.post(url=webhook, data=data, headers=header)
    
    
############# requests 安全链接  
from functools import wraps 
 
def retry(retries=5, delay=5):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            for attempt in range(retries):
                try:
                    return func(*args, **kwargs)
                except requests.exceptions.RequestException  as e:
                    if attempt == retries - 1:
                        raise e 
                    time.sleep(delay) 
            return None 
        return wrapper 
    return decorator 
 
@retry(retries=5, delay=5)
def safe_request(url, **kwargs):
    response = requests.get(url,  **kwargs)
    response.raise_for_status() 
    return response 

def test_proxy():
    proxies = {'http': vps_proxy_ip,
            'https': vps_proxy_ip
            }
    url = "http://www.baidu.com/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/69.0.3497.100 Safari/537.36'
    }
    try:
        response = requests.get(url, headers=headers, proxies=proxies, timeout=5)
        #print(response.text)
    except Exception as e:
        print(f"请求失败，代理IP无效！{e}")
    else:
        print("请求成功，代理IP有效！")
        
def use_proxy():
    os.environ["http_proxy"] = "http://"+vps_proxy_ip
    os.environ["https_proxy"] = "http://"+vps_proxy_ip
    test_proxy()
