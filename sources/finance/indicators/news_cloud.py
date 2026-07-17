import akshare as ak
import pandas as pd
import re
from collections import Counter
from .base import BaseIndicator
from datetime import datetime, timedelta

class NewsIndicator(BaseIndicator):
    """新闻联播云图 - 关键词分析"""
    def fetch_data(self) -> pd.DataFrame:
        try:
            # CCTV is the only accepted source here; a single-stock news fallback
            # would silently change this indicator's meaning.
            today = datetime.now()
            for i in range(7):
                target_date = (today - timedelta(days=i)).strftime('%Y%m%d')
                try:
                    self.logger.info(f"Fetching CCTV News for {target_date}...")
                    df = ak.news_cctv(date=target_date)
                    if not df.empty:
                        df = df.rename(columns={'标题': 'title', '内容': 'content', 'date': 'date', '日期': 'date'})
                        if 'title' not in df.columns or 'content' not in df.columns:
                            raise ValueError(f"CCTV 新闻字段变化: {list(df.columns)}")
                        df['date'] = pd.to_datetime(target_date)
                        df['news_count'] = len(df)
                        return df
                except:
                    continue
            
            return pd.DataFrame(columns=['date', 'title', 'content', 'news_count'])
        except Exception as e:
            self.logger.error(f"News Fetch Error: {e}")
            raise e

    def _extract_keywords(self, df: pd.DataFrame) -> str:
        # Combined text for wordcloud
        text = " ".join(df['title'].astype(str)) + " " + " ".join(df['content'].astype(str))
        return text

    def plot(self, df: pd.DataFrame) -> str:
        import jieba
        import wordcloud
        import numpy as np
        from PIL import Image
        import os
        
        text = self._extract_keywords(df)
        if not text:
            return ""

        stop_words = {'进行', '已经', '目前', '对于', '开展', '工作', '加强', '推进', '重要', '发展', '建设', '要把', 
                      '我们', '他们', '这些', '这个', '那个', '因为', '所以', '如果', '而且', '这样', '通过', '一致',
                      '表示', '强调', '指出', '会议', '活动', '发表', '讲话', '举行', '深入', '坚持', '必须',
                      '全面', '提升', '持续', '有力', '积极', '共同', '广泛', '不仅', '而且', '一个', '两个', '三个',
                      '实现', '做好', '不断', '发挥', '提出', '要求', '进一步'}
        
        # WordCloud implementation with Mask
        font_path = self.plotter.cjk_font_path
        if not font_path:
            raise RuntimeError('未找到可用于新闻词云的中文字体')
        mask_path = '/nfs/python/push/cloud/utils/china.jpg'
        
        mask = None
        if os.path.exists(mask_path):
            mask = np.array(Image.open(mask_path))
        
        # Cut text
        words = jieba.lcut(text)
        words_str = " ".join([w for w in words if len(w) > 1 and w not in stop_words])
        
        wc = wordcloud.WordCloud(
            font_path=font_path,
            width=1200,
            height=600,
            mode='RGBA',
            background_color=None,
            max_words=100,
            mask=mask,
            contour_width=2,
            contour_color='#e94560', # Neon Red
            colormap='cool', # Cool gradient (Blue to Cyan)
            prefer_horizontal=0.9
        )
        
        wc.generate(words_str)
        
        path = "output/finance/news_cloud.png"
        wc.to_file(path)
        return path
