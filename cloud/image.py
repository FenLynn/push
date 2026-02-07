from .config import *
from .net import *
from .time import *
import random
import time
import requests
import json
import base64
import numpy as np
import cv2
from io import BytesIO

def upload_image_to_cdn(image_path,is_compress=0,target_size=150,_cdn=1): 
    if is_vps:
        url=upload_image_to_smms(image_path=image_path,is_compress=is_compress,target_size=target_size,_cdn=_cdn)
    else:
        url=upload_image_to_github(image_path=image_path, is_compress=is_compress, target_size=target_size,_cdn=_cdn)
    return url

def upload_image_to_smms(image_path, is_compress=0, target_size=150, _cdn=1):
    """
    Upload to SMMS with retry logic and CDN optimization.
    Stats: 3 retries, random 1-10s delay.
    """
    if is_compress:
        pic_compress(pic_path=image_path, out_path=image_path, target_size=target_size)
    
    headers = {'Authorization': smms_token}
    url = 'https://smms.app/api/v2/upload'
    
    final_url = ""
    max_retries = 3
    
    print(f"Info: Starting upload for {image_path} (Max retries: {max_retries})")

    for i in range(max_retries):
        try:
            files = {'smfile': open(image_path, 'rb')}
            res = requests.post(url, files=files, headers=headers, timeout=30).json()
            
            if res.get('success'):
                final_url = res['data']['url']
                print(f"Info: Upload success on round {i+1}")
                break
            elif res.get('code') == 'image_repeated':
                final_url = res['images']
                print(f"Info: Image already exists at {final_url}")
                break
            else:
                print(f"Warning: Upload failed on round {i+1}. Message: {res.get('message')}")
        
        except Exception as e:
            print(f"Warning: Exception on round {i+1}: {e}")
        
        # Random backoff if not last attempt
        if i < max_retries - 1:
            wait_time = random.randint(1, 10)
            print(f"Info: Waiting {wait_time}s before retry...")
            time.sleep(wait_time)
            
    if not final_url:
        print(f"Error: Failed to upload {image_path} after {max_retries} attempts.")
        return None
        
    print(f"Info: Final SMMS URL: {final_url}")
    
    # CDN handling
    if _cdn:
        return cdn(final_url)
    return final_url

def upload_image_to_github(image_path, is_compress=0, target_size=150, _cdn=1) -> str:
    # 配置参数（需用户修改部分）
    config = {  
        "token": g_token,
        "username": g_owner,
        "repo": g_repo,
        "branch": g_branch,
        "cdn_domain": g_cdn[random.randint(0,4)],
        "proxy": proxy_ip[0]  # 代理地址需自行配置
    }
    time.sleep(1)
    if is_compress:
        pic_compress(pic_path=image_path, out_path=image_path, target_size=target_size)

    def check_proxy_available():
        """检查代理服务器连通性"""
        try:
            test_url = "https://api.github.com/zen"
            proxies = {"http": config["proxy"], "https": config["proxy"]}
            response = requests.get(test_url, proxies=proxies, timeout=5)
            return response.status_code == 200
        except:
            return False

    # 核心上传逻辑
    try:
        with open(image_path, "rb") as f:   # 第一阶段：无代理上传尝试
            encoded_image = base64.b64encode(f.read()).decode('utf-8')
        filename = 'pic/{0}.{1}'.format(get_time_ymdhms_str(),image_path.split(".")[-1])  #filename = os.path.basename(image_path)
        mylog.debug(filename)
        api_url = f"https://api.github.com/repos/{config['username']}/{config['repo']}/contents/{filename}"
        headers = {
            "Authorization": f"token {config['token']}",
            "Accept": "application/vnd.github.v3+json"
        }
        data = {
            "message": "auto upload",
            "content": encoded_image,
            "branch": config['branch']
        }
        
        response = requests.put(api_url, json=data, headers=headers, timeout=10)  # 首次无代理上传
        
        if response.status_code == 201:
            image_url=response.json()['content']['html_url']
            cdn_url=f"https://{config['cdn_domain']}/gh/{config['username']}/{config['repo']}@{config['branch']}/{filename}"
            print (cdn_url)
            return cdn_url
        else:
            raise Exception(f"API Error: {response.json().get('message')}")

    except requests.exceptions.RequestException as e:  # 第二阶段：代理重试逻辑
        if not check_proxy_available():  
            return "0"  # 代理不可用直接返回
        try:
            proxies = {"http": config["proxy"], "https": config["proxy"]}   # 使用代理重试上传
            response = requests.put(api_url, json=data, headers=headers, proxies=proxies, timeout=15)
            if response.status_code == 201:
                image_url=response.json()['content']['html_url']
                cdn_url=f"https://{config['cdn_domain']}/gh/{config['username']}/{config['repo']}@{config['branch']}/{filename}"
                print (cdn_url)
                return cdn_url
            else:
                return ""  # 代理连接成功但API错误
        except requests.exceptions.RequestException:
            return ""  # 代理网络错误
    except Exception as e:
        return ""
    return ""

def pic_compress(pic_path='./test.jpg', out_path='./test.jpg', target_size=199, quality=99, step=5, pic_type='.jpg'):
    # 读取图片bytes
    with open(pic_path, 'rb') as f:
        pic_byte = f.read()
    img_np = np.frombuffer(pic_byte, np.uint8)
    img_cv = cv2.imdecode(img_np, cv2.IMREAD_ANYCOLOR)
    current_size = len(pic_byte) / 1024
    
    while current_size > target_size:
        pic_byte = cv2.imencode(pic_type, img_cv, [int(cv2.IMWRITE_JPEG_QUALITY), quality])[1]
        if quality - step < 0:
            break
        quality -= step
        current_size = len(pic_byte) / 1024
    # 保存图片
    with open(out_path, 'wb') as f:
        f.write(BytesIO(pic_byte).getvalue())
    return len(pic_byte) / 1024


def cdn(_url):        
    _cdn_request_url='https://api.zxz.ee/api/imgcdn/?url={}'.format(_url)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36"
    }
    try:
        response = requests.get(_cdn_request_url, headers=headers, timeout=10)
        data = response.json()
        if data.get('code') == 200:
            print(f"Info: CDN Success -> {data['url']}")
            return data['url']
        else:
            print(f"Warning: CDN Failed ({data.get('msg', 'unknown')}), using original: {_url}")
            return _url
    except Exception as e:
        print(f"Warning: CDN Exception {e}, using original: {_url}")
        return _url

# ... Plot helper functions (fmt_demical, pic1_fmt etc) maintained ...
def fmt_demical(_df,column_list=[],num=2):
    for i in column_list:
        _df[i]=round(_df[i],2)
    return _df

def fmt_no(num,ndem=2):
    return round(num,2)

def pic1_fmt(fig,axes,title='',xlabel='x',ylabel='y',rotation=15,sci_on=False):
    axes.set_title(title,fontsize=24)
    axes.grid(linestyle='--')
    axes.set_xlabel(xlabel,fontsize=18) 
    axes.set_ylabel(ylabel,fontsize=16)
    plt.setp(axes.get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes.tick_params(axis = 'y', which = 'major', labelsize = 12,top=True,right=True) 
    axes.legend(loc='best',fontsize = 16,frameon=False)
    if sci_on:
        axes.ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic11_fmt(fig,axes,axes2,title='',xlabel='x',ylabel1='y1',ylabel2='y2',rotation=15,sci_on=False,set_label_y_color=True):
    axes.set_title(title,fontsize=24)
    axes.grid(linestyle='--')
    axes.set_xlabel(xlabel,fontsize=18) 
    axes2.spines['left'].set_visible(False)
    if set_label_y_color:
        axes.set_ylabel(ylabel1,color=mycolors[0],fontsize=16)
        axes2.set_ylabel(ylabel2,color=mycolors[1],fontsize=16)
        axes.spines['left'].set_color(mycolors[0])
        axes2.spines['right'].set_color(mycolors[1])
        axes.tick_params(axis = 'y', which = 'major', labelsize = 12, colors=mycolors[0]) 
        axes2.tick_params(axis = 'y', which = 'major', labelsize = 12, colors=mycolors[1]) 
        axes.tick_params(top=True)
        axes2.tick_params(top=True)
    else:
        axes.set_ylabel(ylabel1,fontsize=16)
        axes2.set_ylabel(ylabel2,fontsize=16)
        axes.tick_params(axis = 'y', which = 'major', labelsize = 12) 
        axes2.tick_params(axis = 'y', which = 'major', labelsize = 12)       
        axes.tick_params(top=True)
        axes2.tick_params(top=True)         
    plt.setp(axes.get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes.legend(loc='best',fontsize = 16,frameon=False)
    if sci_on:
        axes.ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes2.ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic12_fmt(fig,axes,title='',xlabel='x',ylabel='y',rotation=15,sci_on=False,set_label_y_color=True):
    plt.subplots_adjust(wspace = 0, hspace = 0 )
    fig.suptitle(title,fontsize=24)
    axes[0].grid(linestyle='--')
    axes[1].grid(linestyle='--')
    axes[0].set_xlabel(xlabel,fontsize=18) 
    if set_label_y_color:
        axes[0].set_ylabel(ylabel,fontsize=16,color=mycolors[0])
        axes[1].set_ylabel(ylabel,fontsize=16,color=mycolors[1])
        axes[0].spines['left'].set_color(mycolors[0])
        axes[1].spines['right'].set_color(mycolors[1])
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[0]) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[1])
    else:
        axes[0].set_ylabel(ylabel,fontsize=16)
        axes[1].set_ylabel(ylabel,fontsize=16)
        axes[0].tick_params(axis = 'both', which = 'both', labelsize = 12) 
        axes[1].tick_params(axis = 'both', which = 'both', labelsize = 12)
    
    axes[0].tick_params(top=True,right = True)
    axes[1].tick_params(labelleft=False,labeltop=False,labelright = True,right = True,top=True)
    axes[1].yaxis.set_label_position("right")
    plt.setp(axes[0].get_xticklabels(), rotation=rotation, horizontalalignment='right')
    plt.setp(axes[1].get_xticklabels(), rotation=90, horizontalalignment='right')
    axes[0].legend(loc='best',fontsize = 12,frameon=False)
    if sci_on:
        axes[0].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[1].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic21_fmt(fig,axes,title='',xlabel='x',ylabel1='y',ylabel2='y',rotation=15,sci_on=False,set_label_y_color=True):
    plt.subplots_adjust(wspace = 0, hspace = 0 )
    axes[0].set_title(title,fontsize=24)
    axes[0].grid(linestyle='--')
    axes[1].grid(linestyle='--')
    axes[1].set_xlabel(xlabel,fontsize=18) 
    if set_label_y_color:
        axes[0].set_ylabel(ylabel1,fontsize=16,color=mycolors[0])
        axes[1].set_ylabel(ylabel2,fontsize=16,color=mycolors[1])
        axes[0].spines['left'].set_color(mycolors[0])
        axes[1].spines['left'].set_color(mycolors[1])
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[0]) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[1])
    else:
        axes[0].set_ylabel(ylabel1,fontsize=16)
        axes[1].set_ylabel(ylabel2,fontsize=16)
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12)
    axes[0].tick_params(top=True,right = True)
    axes[1].tick_params(top=True,right = True)
    plt.setp(axes[1].get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes[0].legend(loc='best',fontsize = 12,frameon=False)
    axes[1].legend(loc='best',fontsize = 12,frameon=False)
    if sci_on:
        axes[0].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[1].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def pic31_fmt(fig,axes,title='',xlabel='x',ylabel1='y',ylabel2='y2',ylabel3='y3',rotation=15,sci_on=False,set_label_y_color=True):
    plt.subplots_adjust(wspace = 0, hspace = 0 )
    axes[0].set_title(title,fontsize=24)
    axes[0].grid(linestyle='--')
    axes[1].grid(linestyle='--')
    axes[2].grid(linestyle='--')
    axes[2].set_xlabel(xlabel,fontsize=18) 
    if set_label_y_color:
        axes[0].set_ylabel(ylabel1,fontsize=16,color=mycolors[0])
        axes[1].set_ylabel(ylabel2,fontsize=16,color=mycolors[1])
        axes[2].set_ylabel(ylabel3,fontsize=16,color=mycolors[2])
        axes[0].spines['left'].set_color(mycolors[0])
        axes[1].spines['left'].set_color(mycolors[1])
        axes[2].spines['left'].set_color(mycolors[2])        
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[0]) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[1])
        axes[2].tick_params(axis = 'y', which = 'both', labelsize = 12, colors=mycolors[2])
    else:
        axes[0].set_ylabel(ylabel1,fontsize=16)
        axes[1].set_ylabel(ylabel2,fontsize=16)
        axes[2].set_ylabel(ylabel3,fontsize=16)
        axes[0].tick_params(axis = 'y', which = 'both', labelsize = 12) 
        axes[1].tick_params(axis = 'y', which = 'both', labelsize = 12)
        axes[2].tick_params(axis = 'y', which = 'both', labelsize = 12)
    axes[0].tick_params(top=True,right = True)
    axes[1].tick_params(top=True,right = True)
    axes[2].tick_params(top=True,right = True)
    plt.setp(axes[2].get_xticklabels(), rotation=rotation, horizontalalignment='right')
    axes[0].legend(loc='best',fontsize = 12,frameon=False)
    axes[1].legend(loc='best',fontsize = 12,frameon=False)
    axes[2].legend(loc='best',fontsize = 12,frameon=False)
    if sci_on:
        axes[0].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[1].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
        axes[2].ticklabel_format(style='sci', scilimits=(-1,2), axis='y')
    fig.tight_layout()

def current_line(current_value,axes,color='green',xlim=[]):
    if len(xlim) == 0:
        xaxis_lim=axes.get_xlim()
    else:
        xaxis_lim=xlim
    axes.hlines(current_value,xaxis_lim[0],xaxis_lim[1],linestyle='--',linewidth=0.8,color=color,zorder=5)