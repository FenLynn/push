"""
English Module - 每日英语
从原 morning/main.py 提取
"""
import requests
import json
import time
from bs4 import BeautifulSoup
from typing import Tuple


def get_daily_english() -> Tuple[str, str]:
    """
    获取每日英语
    
    Returns:
        Tuple[str, str]: (iciba句子, shanbay句子)
    """
    def get_iciba():
        try:
            url = 'http://open.iciba.com/dsapi/'
            res = requests.get(url, timeout=10)
            content_e = res.json()['content']
            content_c = res.json()['note']
            return content_e + " " + content_c
        except:
            return ""

    def get_shanbay(str_date=""):
        try:
            str_date_current = time.strftime("%Y-%m-%d", time.localtime())
            date_base_formatted = str_date if str_date else str_date_current
            
            str_url = "https://apiv3.shanbay.com/weapps/dailyquote/quote/?date=" + date_base_formatted
            obj_resp = requests.get(str_url, timeout=10)
            obj_resp_data = obj_resp.text
            data_html_json = json.loads(obj_resp_data)
            data_content_en = dict(data_html_json).get('content')
            data_content_zh = dict(data_html_json).get('translation')
            return (data_content_en + " " + data_content_zh)
        except:
            return ""
    
    return get_iciba(), get_shanbay()
