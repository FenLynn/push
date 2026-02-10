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
    
    TEST_MODE = False
    TEST_JOURNALS = ['Optics Express', 'Optics Letters', 'Applied Optics', 'Photonics Research']
    TEST_ARTICLES_PER_JOURNAL = 15
    TEST_SKIP_MARK_READ = True
    
    @staticmethod
    def to_chinese_num(n):
        chinese_nums = ['零', '一', '二', '三', '四', '五', '六', '七', '八', '九', '十']
        if n <= 10: return chinese_nums[n]
        return str(n)

    @staticmethod
    def to_roman_num(n):
        roman_map = [(10, 'X'), (9, 'IX'), (5, 'V'), (4, 'IV'), (1, 'I')]
        result = ""
        for val, symbol in roman_map:
            while n >= val:
                result += symbol
                n -= val
        return result

    def __init__(self, topic='me', test_mode=None):
        super().__init__()
        self.topic = topic
        self.test_mode = test_mode if test_mode is not None else self.TEST_MODE
    
    MAX_ARTICLES_PER_PAGE = 35
    
    def run(self) -> list:
        """
        生成论文报告，支持分段推送
        
        Returns:
            list: Message 对象列表
        """
        # 获取论文数据
        today_info = self._get_data()
        
        if today_info['articles_sum'] == 0:
            html_content = self._generate_html(today_info)
            title = f'光学文献{time.strftime("%m-%d", time.localtime())}'
            return [Message(
                title=title,
                content=html_content,
                type=ContentType.HTML,
                tags=['paper', 'academic', self.topic],
            )]

    MAX_PAGE_SIZE = 19500 # 极限逼近 20k
    
    def _estimate_article_size(self, article):
        """预估单条文章的 HTML 字符数"""
        size = 150 # 基础 HTML 标签开销 (扁平化后降低)
        size += len(article.get('title', '')) * 1.5 # 进一步降低权重
        size += len(article.get('link', ''))
        size += 50 # 其他字段余量
        return size

    def run(self) -> list:
        """运行获取流程并返回消息列表"""
        today_info = self._get_data()
        if not today_info['paper']:
            return []
            
        # 分段逻辑 - 动态长度适配
        all_pages = []
        current_papers = []
        current_page_size = 500
        
        for feed in today_info['paper']:
            articles = feed['data']
            if not articles: continue
            
            journal_articles_to_page = []
            for art in articles:
                est_size = self._estimate_article_size(art)
                
                # 如果加上当前文章超过页限制
                if current_page_size + est_size > self.MAX_PAGE_SIZE:
                    # 先结算当前期刊已经在攒的文章（如果有）
                    if journal_articles_to_page:
                        current_papers.append({
                            'journal': feed['journal'],
                            'data': journal_articles_to_page,
                            'articles_nu': len(journal_articles_to_page)
                        })
                        journal_articles_to_page = []
                    
                    # 结算当前页
                    if current_papers:
                        all_pages.append(current_papers)
                        current_papers = []
                        current_page_size = 500
                
                journal_articles_to_page.append(art)
                current_page_size += est_size
            
            # 期刊遍历完，如果还有剩余文章，存入 current_papers
            if journal_articles_to_page:
                current_papers.append({
                    'journal': feed['journal'],
                    'data': journal_articles_to_page,
                    'articles_nu': len(journal_articles_to_page)
                })

        # 全天处理完，手动结算最后一页
        if current_papers:
            all_pages.append(current_papers)
            
        # 生成消息列表
        # 重写 run() 的分页循环部分
        messages = []
        global_idx = 1
        journal_page_tracker = {} # j_name -> current_page_index
        
        # 预先计算每个期刊在总分页中出现的次数，用于决定是否显示罗马数字
        journal_total_pages = {} # j_name -> total_occurrences
        for pg in all_pages:
            for f in pg:
                journal_total_pages[f['journal']] = journal_total_pages.get(f['journal'], 0) + 1

        total_pages = len(all_pages)
        base_title = f'光学文献{time.strftime("%m-%d", time.localtime())}'
        
        for idx, page_papers in enumerate(all_pages):
            is_first_page = (idx == 0)
            
            # 处理分页标签和全局序号
            for f_item in page_papers:
                j_name = f_item['journal']
                count = journal_page_tracker.get(j_name, 0) + 1
                journal_page_tracker[j_name] = count
                
                # 如果这个期刊总共会出现多次，则打上罗马数字标签
                if journal_total_pages[j_name] > 1:
                    f_item['page_label'] = self.to_roman_num(count)
                else:
                    f_item['page_label'] = ""
                
                # 设置全天总文章数
                f_item['total_nu'] = next(p['articles_nu'] for p in today_info['paper'] if p['journal'] == j_name)
                
                # 设置中文序号 (基于原始期刊列表的顺序)
                original_idx = next(i for i, p in enumerate(today_info['paper']) if p['journal'] == j_name) + 1
                f_item['chinese_idx'] = self.to_chinese_num(original_idx)

                for article in f_item['data']:
                    article['global_idx'] = global_idx
                    global_idx += 1
            
            # 准备渲染上下文，始终保留全天指标
            page_info = {
                'today': today_info['today'],
                'is_first_page': is_first_page,
                'total_journals': today_info['journals'],
                'total_articles_sum': today_info['articles_sum'],
                'paper': page_papers,
            }
            
            # 渲染模板
            html_content = self._generate_html(page_info)
            
            # 标题处理
            title = base_title
            if total_pages > 1:
                title += f'({idx+1}/{total_pages})'
            
            messages.append(Message(
                title=title,
                content=html_content,
                type=ContentType.HTML,
                tags=['paper', 'academic', self.topic],
                metadata={'date': today_info['today'], 'page': idx+1, 'total_pages': total_pages, 'count': sum(f['articles_nu'] for f in page_papers)}
            ))
            
        return messages
    
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
    
    def _get_target_category_id(self, client) -> int:
        """动态获取分类 ID (优先 '科学'，次填 '期刊')"""
        target_names = ["科学", "期刊"]
        try:
            categories = client.get_categories()
            for target_name in target_names:
                for cat in categories:
                    if isinstance(cat, dict):
                        name = cat.get('title')
                        cat_id = cat.get('id')
                    else:
                        name = getattr(cat, 'title', None)
                        cat_id = getattr(cat, 'id', None)
                    
                    if name == target_name:
                        print(f"[Paper] Found category '{target_name}' with ID: {cat_id}")
                        return int(cat_id)
            
            print(f"[Paper] Warning: Targeted categories {target_names} not found. Using default (-1 or ALL).")
        except Exception as e:
            print(f"[Paper] Error fetching categories: {e}")
            
        return -1 # -1 usually means Special/All or root
    
    def _get_data(self) -> dict:
        """获取论文数据"""
        try:
            client = self._login()
        except Exception as e:
            print(f"[Paper] Login failed: {e}")
            return {
                "journals": 0, 
                "today": datetime.now().strftime("%Y-%m-%d"), 
                "articles_sum": 0, 
                "journals_title": [], 
                "paper": []
            }
        
        # 动态获取分类 ID
        _ID = self._get_target_category_id(client)
        print(f'[Paper] Using TTRSS cat_id={_ID}')
        
        feed_list = []
        try:
            feeds = client.get_feeds(cat_id=_ID, unread_only=not self.test_mode)
            if self.test_mode:
                # 过滤测试期刊
                all_feeds = feeds
                feeds = [f for f in feeds if f.title in self.TEST_JOURNALS]
                
                if not feeds:
                    print(f'[TEST MODE] No journals matched TEST_JOURNALS. Available in this category: {", ".join([f.title for f in all_feeds[:10]])}')
                    # 如果匹配不到，则取前几个作为演示
                    feeds = all_feeds[:3]
                else:
                    print(f'[TEST MODE] Selected {len(feeds)} journals from TEST_JOURNALS')
            else:
                print(f'Journals with articles: {", ".join([i.title for i in feeds])}')
        except Exception as e:
            print(f"[Paper] Failed to get feeds: {e}")
            feeds = []
        
        # feed_list = [] # Removed redundant decl
        
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
                    }
                except Exception as e:
                    print(f'  Warning: Failed to fetch full article for "{headline.title[:50]}...": {e}')
                    continue
                
                pass
                
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
                
                # 通用期刊需要关键词 (测试模式下跳过筛选)
                if not self.test_mode and feed.title in self.GENERAL_JOURNALS and not paper['is_include_keyword']:
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
            'today': today_info.get('today'),
            'update_time': time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            'is_first_page': today_info.get('is_first_page', True),
            'total_journals': today_info.get('total_journals', 0),
            'total_articles_sum': today_info.get('total_articles_sum', 0),
            'paper': today_info.get('paper', []),
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
