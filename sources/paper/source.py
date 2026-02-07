"""
Paper Source - 学术论文推送
整合原 paper/main.py 的所有功能，适配 IFTTT 架构
"""
import sys
import os
import re
import time
from datetime import datetime, timedelta
from string import Template

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sources.base import BaseSource
from core import Message, ContentType

# 导入原有的 cloud 库
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from cloud import *
from cloud.utils.lib import *

# 导入新的环境配置系统
from core.env import get_env_config


class PaperSource(BaseSource):
    """论文数据源"""
    
    # 关键词配置
    CHN_KEYWORDS = ["光纤", "激光", "高功率", "窄线宽", "受激拉曼散射", "模式不稳定",
                    "受激布里渊散射", "同带泵浦", "合束器", "机器学习", "神经网络",
                    "深度学习", "自旋", "轨道"]
    
    ENG_KEYWORDS = ["fiber", "laser", "narrow linewidth", "tandem", "coherrent",
                    "transverse mode instability", "stimulated Raman scattering",
                    "stimulated Brillouin scattering", "SRS", "SBS", "TMI", "1018 nm",
                    "combiner", "machine learning", "neural network", "deep learning",
                    "orbital angular momentum", "skyrmions", "metafiber", "multimode"]
    
    # 期刊配置
    GENERAL_JOURNALS = ["Scientific Reports", "物理学报", "Micromachines",
                        "Nature Communications", "IEEE Journal of Quantum Electronics"]
    
    MDPI_JOURNALS = ['Micromachines', 'Photonics']
    
    OSA_JOURNALS = ['Optica', 'Optical Materials Express', 'Optics Continuum',
                    'Optics Express', 'Optics Letters', 'Photonics Research',
                    'Journal of Lightwave Technology',
                    'Journal of the Optical Society of America B',
                    'Applied Optics', 'Advances in Optics and Photonics']
    
    MAX_ARTICLES_PER_JOURNAL = 10
    TTRSS_CAT_ID = None
    PAST_HOURS = 25
    
    TEST_MODE = True
    TEST_JOURNALS = ['Optics Express', 'Optics Letters', 'Applied Optics', 
                     'Photonics Research', 'Optics Continuum', 'Optical Materials Express']
    TEST_ARTICLES_PER_JOURNAL = 10
    TEST_SKIP_MARK_READ = True
    
    def __init__(self, topic='me', test_mode=None):
        super().__init__()
        self.topic = topic
        self.test_mode = test_mode if test_mode is not None else self.TEST_MODE
    
    def run(self) -> Message:
        """
        生成论文报告
        
        Returns:
            Message: 论文消息（HTML 格式）
        """
        # 获取论文数据
        today_info = self._get_data()
        
        # 生成 HTML 内容
        html_content = self._generate_html(today_info)
        
        # 构建标题
        title = f'光学文献{time.strftime("%m-%d", time.localtime())}'
        
        return Message(
            title=title,
            content=html_content,
            type=ContentType.HTML,
            tags=['paper', 'academic', self.topic],
            metadata={'date': today_info['today'], 'count': today_info['articles_sum']}
        )
    
    def _get_osa_past_hours(self) -> int:
        """OSA 特殊时间处理"""
        now = datetime.now()
        zeroToday = now - timedelta(hours=now.hour, minutes=now.minute,
                                     seconds=now.second, microseconds=now.microsecond)
        osaToday = zeroToday + timedelta(hours=13, minutes=0, seconds=0)
        _diff = (now - osaToday)
        total_hours = int(_diff.total_seconds() / 3600) + 25
        return total_hours
    
    def _login(self):
        """登录 TTR RSS - 使用环境配置"""
        env_config = get_env_config()
        
        url = env_config.get('network', 'ttrss_url')
        username = env_config.get('network', 'ttrss_username')
        password = env_config.get('network', 'ttrss_password', default=ttrss_password)
        
        print(f"[Paper] Connecting to TTR RSS: {url}")
        client = TTRClient(url, username, password, auto_login=True)
        client.login()
        return client
    
    def _include_keywords(self, paper) -> tuple:
        """检查论文是否包含关键词"""
        total_keywords = self.CHN_KEYWORDS + self.ENG_KEYWORDS
        
        def find_keywords(text, keywords):
            keyword_pattern = re.compile("|".join(keywords), re.IGNORECASE)
            matches = keyword_pattern.findall(text)
            return matches
        
        found_title = find_keywords(paper['title'], total_keywords)
        found_abstract = find_keywords(paper['content'], total_keywords)
        
        found_unique = list(set([i.lower() for i in (found_title + found_abstract)]))
        
        has_keyword = len(found_title) > 0 or len(found_abstract) > 0
        return has_keyword, found_unique
    
    def _filter_date(self, paper, journal_title) -> bool:
        """根据时间过滤论文"""
        _today = datetime.now()
        _dtime = paper['datetime']
        diff = _today - _dtime
        
        _past_hours = (self._get_osa_past_hours()
                       if journal_title in self.OSA_JOURNALS
                       else self.PAST_HOURS)
        
        return diff < timedelta(hours=_past_hours)
    
    def _get_data(self) -> dict:
        """获取论文数据"""
        
        client = self._login()
        
        # 确定 TTRSS 分类ID
        if self.TTRSS_CAT_ID is not None:
            _ID = self.TTRSS_CAT_ID
        else:
            # 根据环境自动检测：local环境用6，vps环境用2
            env_config = get_env_config()
            env_name = env_config.env_name if hasattr(env_config, 'env_name') else 'local'
            _ID = 2 if env_name == 'vps' else 6
        
        print(f'[Paper] Using TTRSS cat_id={_ID}')
        
        if self.test_mode:
            feeds = client.get_feeds(cat_id=_ID, unread_only=False)
            feeds = [f for f in feeds if f.title in self.TEST_JOURNALS]
            print(f'[TEST MODE] Selected {len(feeds)} journals: {", ".join([f.title for f in feeds])}')
        else:
            feeds = client.get_feeds(cat_id=_ID, unread_only=True)
            print(f'Journals with articles: {", ".join([i.title for i in feeds])}')
        
        feed_list = []
        
        for feed in feeds:
            print(f'Processing {feed.title}...')
            data_list = []
            ino = 1
            
            headlines = list(feed.headlines())
            
            if self.test_mode:
                headlines = headlines[:self.TEST_ARTICLES_PER_JOURNAL]
                print(f'  [TEST] Processing {len(headlines)} articles')
            
            for headline in headlines:
                if not self.test_mode and not headline.unread:
                    continue
                
                article_id = headline.id
                if not self.test_mode and not self.TEST_SKIP_MARK_READ:
                    client.toggle_unread([article_id])


                # 获取完整文章（用于摘要和时间）
                try:
                    full_article = headline.full_article()
                    paper = {
                        'id': ino,
                        'title': headline.title,
                        'link': headline.link,
                        'datetime': full_article.updated,
                        'content': full_article.content if hasattr(full_article, 'content') else '',
                        'author': full_article.author if hasattr(full_article, 'author') else ''
                    }
                except Exception as e:
                    print(f'  Warning: Failed to fetch full article for "{headline.title[:50]}...": {e}')
                    continue
                
                # 处理作者格式: Only first author + et al.
                if paper['author']:
                    initial_authors = paper['author'].split(',')
                    if len(initial_authors) > 1:
                        paper['author'] = f"{initial_authors[0].strip()} et al."
                    else:
                        paper['author'] = initial_authors[0].strip()
                
                # 清理标题
                paper['title'] = paper['title'].replace(f"【{feed.title}】", '')
                if feed.title in self.MDPI_JOURNALS:
                    pat = f'^{feed.title}, Vol. [0-9]*, Pages [0-9]*: '
                    matchResult = re.findall(pat, paper['title'])
                    if matchResult:
                        paper['title'] = paper['title'].replace(matchResult[0], '')
                
                # 关键词检测
                paper['is_include_keyword'], paper['keywords'] = self._include_keywords(paper)
                
                # 时间过滤（测试模式跳过）
                if not self.test_mode and not self._filter_date(paper, feed.title):
                    ino += 1
                    continue
                
                # 通用期刊需要关键词
                if feed.title in self.GENERAL_JOURNALS and not paper['is_include_keyword']:
                    ino += 1
                    continue
                
                data_list.append(paper)
                ino += 1
            
            feed_list.append({
                "journal": feed.title,
                "data": data_list,
                "articles_nu": len(data_list)
            })
            print(f'{feed.title}: {len(data_list)} 篇')
        
        # 统计信息
        today_info = {
            "journals": 0,
            "today": datetime.now().date().strftime("%Y-%m-%d"),
            "articles_sum": 0,
            "journals_title": [],
            "paper": feed_list
        }
        
        for feed_data in feed_list:
            today_info["articles_sum"] += feed_data["articles_nu"]
            if feed_data["articles_nu"] > 0:
                today_info["journals_title"].append(feed_data["journal"])
                today_info["journals"] += 1
        
        return today_info
    
    def _generate_html(self, today_info) -> str:
        """
        使用 Jinja2 模板生成 HTML 内容
        """
        import time
        from jinja2 import Environment, FileSystemLoader
        
        # 加载模板
        template_dir = os.path.join(os.path.dirname(__file__), '../../templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        
        try:
            template = env.get_template('paper.html')
        except Exception as e:
            self.logger.warning(f"Cannot load paper.html template: {e}, using legacy format")
            return self._generate_html_legacy(today_info)
        
        # 渲染模板
        context = {
            'today': today_info['today'],
            'update_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            'journals': today_info['journals'],
            'articles_sum': today_info['articles_sum'],
            'journals_title': today_info['journals_title'],
            'paper': today_info['paper'],
        }
        
        return template.render(**context)
    
    def _generate_html_legacy(self, today_info) -> str:
        """
        旧版 HTML 生成（备用）
        """
        head_html = """<html><head><style>
table th {font-weight: bold; text-align: center !important; background: rgba(158,188,226,0.2); white-space: wrap;}
table tbody tr:nth-child(2n) { background-color: #f2f2f2;}
table{font-family: Arial, sans-serif; font-size: 12px;}
html{font-family:sans-serif;}
table{border-collapse:collapse;}
td,th{border:1px solid rgb(190,190,190);padding:1px 2px;line-height:1.3em;}
</style><meta charset="utf-8"></head>"""
        
        # 无更新情况
        if today_info["articles_sum"] <= 0:
            return f'{head_html}<font size="3">🕔今天{today_info["today"]}, 无光学文章更新.</font></html>'
        
        # 有更新
        content = head_html
        content += f'🕔更新时间:{time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())} \n'
        content += f'⏺ 共<font color="cadetblue"><b>{today_info["journals"]}</b></font>本期刊, '
        content += f'<font color="cadetblue"><b>{today_info["articles_sum"]}</b></font>篇文章更新.</font></br>'
        
        table_template = '<table><tr align=center><th style="min-width:25px">序</th><th style="min-width:270px">文章标题</th><th style="min-width:50px">关键词</th></tr>${CONTENT}</table>'
        
        ino = 1
        for feed_data in today_info["paper"]:
            if len(feed_data["data"]) == 0:
                continue
            
            content += f' <font size="2" color="cadetblue"><b>{feed_data["journal"]}</b></font> '
            content += f'<font size="2"><b>  {feed_data["articles_nu"]}</b>篇</font></br>'
            
            rows = ""
            for paper in feed_data["data"]:
                if paper["is_include_keyword"]:
                    align = 'left' if len(",".join(paper['keywords'])) > 9 else 'center'
                    rows += f'<tr style="color: indianred;"><td align="center">{ino}</td>'
                    rows += f'<td align="left"><a href="{paper["link"]}" target="_blank"><font color="indianred">{paper["title"]}</font></a></td>'
                    rows += f'<td align={align}>{" ".join(paper["keywords"])}</td></tr>'
                else:
                    rows += f'<tr style="color: gray;"><td align="center">{ino}</td>'
                    rows += f'<td align="left"><a href="{paper["link"]}" target="_blank"><font color="gray">{paper["title"]}</font></a></td>'
                    rows += f'<td align="center">无</td></tr>'
                ino += 1
            
            table_html = Template(table_template).safe_substitute({'CONTENT': rows})
            content += table_html + '</br>'
        
        content += '</html>'
        return content



if __name__ == '__main__':
    # 独立测试
    source = PaperSource(topic='me')
    msg = source.run()
    print(f"Title: {msg.title}")
    print(f"Type: {msg.type}")
    print(f"Content length: {len(msg.content)} chars")
    print(f"Metadata: {msg.metadata}")
