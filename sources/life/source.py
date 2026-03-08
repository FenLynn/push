"""Life Source - 娱乐风向标 (Life V2)"""
import sys, os, time
import pandas as pd
import akshare as ak
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sources.base import BaseSource
from core import Message, ContentType
from core.template import TemplateEngine
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from core.legacy import *
from core.utils.lib import *

class LifeSource(BaseSource):
    """娱乐数据源 (电影/电视剧/综艺)"""
    def __init__(self, topic='me', **kwargs):
        super().__init__(**kwargs)
        self.topic = topic
        self.template = TemplateEngine()
    
    def run(self) -> Message:
        data = self._get_combined_data()
        
        # Render HTML
        html = self.template.render('life.html', {
            'title': '娱乐风向标',
            'date': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            'box_real': data.get('box_real', []),
            'box_year': data.get('box_year', []),
            'tv_list': data.get('tv_list', []),
            'show_list': data.get('show_list', []),
            'douban_list': data.get('douban_list', []),
            'douban_high_rate': data.get('douban_high_rate', []),
            'book_list': data.get('book_list', [])
        })
        
        # Minify
        html = html.replace('\n', '').replace('  ', '')
        
        return Message(
            title=f'娱乐风向标({time.strftime("%m-%d", time.localtime())})', 
            content=html, 
            type=ContentType.HTML, 
            tags=['life', 'movie', self.topic]
        )
    
    def _get_combined_data(self):
        return {
            'box_real': self._get_movie_realtime(),
            'box_year': self._get_movie_yearly(),
            'tv_list': self._get_tv_hot(),
            'show_list': self._get_show_hot(),
            'douban_list': self._get_douban_hot(),
            'douban_high_rate': self._get_douban_high_rate(),
            'book_list': self._get_douban_book()
        }
    
    def _get_movie_realtime(self):
        """实时票房 Top 10"""
        try:
            df = ak.movie_boxoffice_realtime()
            df = df.head(10)
            res = []
            for _, row in df.iterrows():
                res.append({
                    'name': row['影片名称'],
                    'box': f"{int(float(row['实时票房']))}", # 万
                    'share': str(row['票房占比']).replace('%', ''),
                    'total': f"{round(float(row['累计票房'])/10000, 2)}", # 亿
                    'days': row['上映天数']
                })
            return res
        except Exception as e:
            print(f"[Life] Movie Realtime Error: {e}")
            return []

    def _get_movie_yearly(self):
        """年度票房 Top 10"""
        try:
            df = ak.movie_boxoffice_yearly(time.strftime("%Y%m%d", time.localtime()))
            df = df.head(10)
            res = []
            for _, row in df.iterrows():
                res.append({
                    'name': row['影片名称'],
                    'box': f"{round(float(row['总票房'])/10000, 2)}", # 亿
                    'avg': int(float(row['平均票价'])),
                    'date': str(row['上映日期']).replace(str(time.localtime().tm_year)+'-', '')
                })
            return res
        except Exception as e:
            print(f"[Life] Movie Yearly Error: {e}")
            return []

    def _get_tv_hot(self):
        """热播剧集 Top 10"""
        try:
            df = ak.video_tv() 
            df = df.sort_values(by='用户热度', ascending=False).head(10)
            res = []
            for _, row in df.iterrows():
                res.append({
                    'name': row['名称'],
                    'type': row['类型'],
                    'hot': int(row['用户热度']),
                    'rate': row['好评度']
                })
            return res
        except Exception as e:
            print(f"[Life] TV Error: {e}")
            return []

    def _get_show_hot(self):
        """热门综艺 Top 10"""
        try:
            df = ak.video_variety_show()
            df = df.sort_values(by='用户热度', ascending=False).head(10)
            res = []
            for _, row in df.iterrows():
                res.append({
                    'name': row['名称'],
                    'type': row['类型'],
                    'hot': int(row['用户热度']),
                    'rate': row['好评度']
                })
            return res
        except Exception as e:
            print(f"[Life] Show Error: {e}")
            return []

    def _get_douban_hot(self):
        """热门新片 Top 10"""
        try:
            import requests
            url = "https://movie.douban.com/j/search_subjects?type=movie&tag=%E7%83%AD%E9%97%A8&sort=recommend&page_limit=10&page_start=0"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://movie.douban.com/explore"
            }
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                res = []
                for item in data.get('subjects', [])[:10]:
                    res.append({
                        'name': item.get('title'),
                        'rate': item.get('rate'),
                        'is_new': item.get('is_new', False)
                    })
                return res
            return []
        except Exception as e:
            print(f"[Life] Douban Error: {e}")
            return []

    def _get_douban_high_rate(self):
        """豆瓣高分 Top 10"""
        try:
            import requests
            url = "https://movie.douban.com/j/search_subjects?type=movie&tag=%E8%B1%86%E7%93%A3%E9%AB%98%E5%88%86&sort=recommend&page_limit=10&page_start=0"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
                "Referer": "https://movie.douban.com/explore"
            }
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                res = []
                for item in data.get('subjects', [])[:10]:
                    res.append({
                        'name': item.get('title'),
                        'rate': item.get('rate'),
                        'is_new': item.get('is_new', False)
                    })
                return res
            return []
        except Exception as e:
            print(f"[Life] Douban High Rate Error: {e}")
            return []

    def _get_douban_book(self):
        """豆瓣非虚构类好书榜 Top 10"""
        try:
            import requests
            url = "https://m.douban.com/rexxar/api/v2/subject_collection/book_nonfiction/items?start=0&count=10"
            headers = {"User-Agent": "Mozilla/5.0", "Referer": "https://m.douban.com/book/"}
            r = requests.get(url, headers=headers, timeout=10)
            if r.status_code == 200:
                data = r.json()
                res = []
                for item in data.get("subject_collection_items", []):
                    res.append({
                        'name': item.get('title'),
                        'rate': item.get('rating', {}).get('value', '暂无')
                    })
                return res
            return []
        except Exception as e:
            print(f"[Life] Douban Book Error: {e}")
            return []
