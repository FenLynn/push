"""
Weather Module - 天气查询
从原 morning/main.py 提取
"""
import requests
import re
from typing import Dict


def get_weather() -> Dict[str, list]:
    """
    获取多城市天气
    
    Returns:
        Dict[str, list]: {城市: [天气, 温度]}
    """
    def get_city_weather(url):
        response = requests.get(url)
        response.encoding = 'utf-8'
        aim = re.findall(
            r'<input type="hidden" id="hidden_title" value="(.*?)月(.*?)日(.*?)时 (.*?)  (.*?)  (.*?)"',
            response.text, re.S
        )
        return aim

    url_dict = {
        '双流': "http://www.weather.com.cn/weather/101270106.shtml",
        '西安': "http://www.weather.com.cn/weather/101110101.shtml",
        '延安': "http://www.weather.com.cn/weather/101110300.shtml",
        '宜都': "http://www.weather.com.cn/weather/101200909.shtml"
    }
    
    temp_weather = {}
    for city, url in url_dict.items():
        try:
            data = get_city_weather(url)
            if data:
                temp_weather[city] = [data[0][4], data[0][5]]
        except Exception as e:
            print(f"[Weather] Failed to get weather for {city}: {e}")
            temp_weather[city] = ["未知", "未知"]
    
    return temp_weather
