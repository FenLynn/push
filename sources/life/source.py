"""Life Source - 娱乐风向标 (Life V2)"""
import sys, os, time
import pandas as pd
import akshare as ak
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from sources.base import BaseSource
from core import Message, ContentType
from core.template import TemplateEngine
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from cloud import *
from cloud.utils.lib import *

class LifeSource(BaseSource):
    """娱乐数据源 (电影/电视剧/综艺)"""
    def __init__(self, topic='me'):
        super().__init__()
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
            'show_list': data.get('show_list', [])
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
            'show_list': self._get_show_hot()
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
                    'box': f"{int(row['实时票房'])}", # 万
                    'share': str(row['票房占比']).replace('%', ''),
                    'total': f"{round(row['累计票房']/10000, 2)}", # 亿
                    'days': row['上映天数']
                })
            return res
        except Exception as e:
            print(f"[Life] Movie Realtime Error: {e}")
            return []

    def _get_movie_yearly(self):
        """年度票房 Top 10"""
        try:
            df = ak.movie_boxoffice_yearly(get_time_ymd_str())
            df = df.head(10)
            res = []
            for _, row in df.iterrows():
                res.append({
                    'name': row['影片名称'],
                    'box': f"{round(row['总票房']/10000, 2)}", # 亿
                    'avg': int(row['平均票价']),
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
