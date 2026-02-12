
import requests
import time
import random
import os
import matplotlib.pyplot as plt
from functools import wraps 
from core.config import config

# Note: server_ip should be in config if needed. 
# cloud/net.py had server_ip = ... (from config)
# 'is_server' logic relied on it.
# We'll assume simple check for now or reimplement properly later.
# For now, let's keep get_host_ip but remove is_server hard dependency on config globals unless config exposes them.

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
    return None

def is_server():
    # Placeholder: Reimplement check logic if needed.
    # Legacy: if get_host_ip() in server_ip
    # We can use os.getenv('IS_VPS')
    return os.getenv('IS_VPS') == '1'
    
def general_proxy():
    if not is_server():
        # Return fallback proxy from config
        return config.get('NETWORK', 'PROXY', fallback='')
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

# Requests Decorators
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
