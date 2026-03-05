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
from core.legacy import *
from core.utils.lib import *

import concurrent.futures
import requests
import feedparser
import xml.etree.ElementTree as ET
from core.env import get_env_config
from core.config import config
from core.llm_factory import LLMFactory


class PaperSource(BaseSource):
    """论文数据源"""
    
    # 关键词配置 (Fallback values if not in INI)
    CHN_KEYWORDS = []
    ENG_KEYWORDS = []
    
    # 期刊配置
    # 通用宽泛期刊列表：这些期刊覆盖面广，只推送命中关键词的文章
    # 光学专业期刊（OE/OL 等）不在此列，全量推送
    GENERAL_JOURNALS = [
        "Nature", "Nature Communications", "Scientific Reports",
        "Physical Review Letters", "物理学报", "Micromachines",
        "IEEE Journal of Quantum Electronics",
    ]
    
    MDPI_JOURNALS = ['Micromachines', 'Photonics']
    
    OSA_JOURNALS = ['Optica', 'Optical Materials Express', 'Optics Continuum',
                    'Optics Express', 'Optics Letters', 'Photonics Research',
                    'Journal of Lightwave Technology',
                    'Journal of the Optical Society of America B',
                    'Applied Optics', 'Advances in Optics and Photonics']
    
    # 单个期刊默认最大展示文章数（可通过环境变量覆盖）
    MAX_ARTICLES_PER_JOURNAL = int(os.getenv('PAPER_MAX_ARTICLES_PER_JOURNAL', 15))
    MAX_PAGE_SIZE = 18000  # Safe limit for PushPlus (max 20k)
    TTRSS_CAT_ID = None
    PAST_HOURS = int(os.getenv('PAPER_PAST_HOURS', 48))
    
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

    def __init__(self, topic='me', test_mode=None, **kwargs):
        super().__init__(**kwargs)
        self.topic = topic
        self.test_mode = test_mode if test_mode is not None else self.TEST_MODE
        
        # Docker 环境自适应
        self.in_docker = self._is_docker()
        if self.in_docker:
            print("[Paper] Running in DOCKER environment")
        
        # Initialize Keywords from Config
        self._load_keywords()
        
        # Initialize LLM Provider
        llm_conf = config.get_llm_config()
        self.llm_provider = LLMFactory.create_provider(llm_conf)
        if self.llm_provider:
            print(f"[Paper] LLM Provider Initialized: {llm_conf.get('provider')}")
        else:
            print("[Paper] LLM Provider NOT initialized")
            
        # Normalize GENERAL_JOURNALS for case-insensitive check
        self._general_journals_lower = [j.lower() for j in self.GENERAL_JOURNALS]

    def _load_keywords(self):
        """从配置文件加载关键词"""
        chn_val = config.get('paper.keywords', 'chn', fallback='')
        eng_val = config.get('paper.keywords', 'eng', fallback='')
        
        if chn_val:
            self.CHN_KEYWORDS = [k.strip() for k in chn_val.split(',') if k.strip()]
        if eng_val:
            self.ENG_KEYWORDS = [k.strip() for k in eng_val.split(',') if k.strip()]
        
        print(f"[Paper] Loaded {len(self.CHN_KEYWORDS)} CHN and {len(self.ENG_KEYWORDS)} ENG keywords from config.")

    def _is_docker(self):
        """判断是否在 Docker 环境中"""
        return os.path.exists('/.dockerenv') or (
            os.path.exists('/proc/1/cgroup') and 
            any('docker' in line for line in open('/proc/1/cgroup'))
        )
    
    MAX_ARTICLES_PER_PAGE = 35
    

    def _estimate_article_size(self, article: dict) -> int:
        """估算单篇文章的 HTML 字符大小"""
        # 统计标题、作者、摘要和链接的字符数
        size = len(article.get('title', '')) + len(article.get('author', ''))
        size += len(article.get('description', '')) or len(article.get('summary', '')) or 0
        size += len(article.get('link', ''))
        return size + 300  # 加上 HTML 标签的开销

    MAX_PAGE_SIZE = 19500 # 极限逼近 20k

    def run(self) -> list:
        """运行获取流程并返回消息列表"""
        today_info = self._get_data()
        # Remove early return to allow "No Update" message generation
            
        # 分段逻辑 - 动态长度适配
        all_pages = []
        current_papers = []
        current_page_size = 500
        
        # Helper to settle current page
        def settle_page():
            nonlocal current_papers, current_page_size
            if current_papers:
                all_pages.append(current_papers)
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
                    settle_page()
                
                journal_articles_to_page.append(art)
                current_page_size += est_size
            
            # 期刊遍历完，如果还有剩余文章，存入 current_papers
            if journal_articles_to_page:
                current_papers.append({
                    'journal': feed['journal'],
                    'data': journal_articles_to_page,
                    'articles_nu': len(journal_articles_to_page)
                })

        # 1.3 Add ArXiv and S2 sections if available
        # Attempts to merge into last page if space allows
        
        extra_feeds = []
        arxiv_data = today_info.get('arxiv', [])
        if arxiv_data:
            extra_feeds.append({
                'journal': 'ArXiv Preprints (领域追踪)',
                'data': arxiv_data,
                'articles_nu': len(arxiv_data)
            })
            
        s2_data = today_info.get('s2', [])
        if s2_data:
            extra_feeds.append({
                'journal': 'Scholar Updates (学者动态)',
                'data': s2_data,
                'articles_nu': len(s2_data)
            })
            
        for feed in extra_feeds:
            # Estimate size
            feed_size = 0
            for art in feed['data']:
                feed_size += self._estimate_article_size(art)
            
            # Check if fits in current page
            if current_page_size + feed_size <= self.MAX_PAGE_SIZE:
                current_papers.append(feed)
                current_page_size += feed_size
            else:
                # Settle current page and start new
                settle_page()
                current_papers.append(feed)
                current_page_size = 500 + feed_size # Reset + feed

        # 全天处理完，手动结算最后一页
        settle_page()

        # Update total counts for metadata and UI header
        virtual_journals = (1 if arxiv_data else 0) + (1 if s2_data else 0)
        virtual_articles = len(arxiv_data) + len(s2_data)
        today_info['journals'] += virtual_journals
        today_info['articles_sum'] += virtual_articles

        base_title = f'学术文献{time.strftime("%m-%d", time.localtime())}'

        # 如果无任何更新，推送一条提醒消息
        if not all_pages:
            html_content = f"""
            <div style="padding: 30px; text-align: center; background-color: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb; margin: 20px;">
                <p style="font-size: 18px; color: #374151; font-weight: bold; margin-bottom: 10px;">今日无最新论文更新</p>
                <p style="font-size: 14px; color: #6b7280;">由于所监测的 RSS 源在过去 {self.PAST_HOURS} 小时内未发布新文章，或未命中您的关键词，因此今日无摘要生成。</p>
            </div>
            """
            return [Message(
                title=base_title,
                content=html_content,
                type=ContentType.HTML,
                tags=['paper', 'academic', self.topic],
                metadata={'date': today_info['today'], 'count': 0}
            )]

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
                if j_name in ['ArXiv Preprints (领域追踪)', 'Scholar Updates (学者动态)']:
                    f_item['total_nu'] = f_item['articles_nu']
                    # 为特殊模块设置专属中文序号或放在最后
                    f_item['chinese_idx'] = "补" if "ArXiv" in j_name else "专"
                else:
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
            
        # 生成一份包含全天所有数据的完整 HTML 用于本地查阅 (OVERWRITE latest.html with FULL data)
        full_info = {
            'today': today_info['today'],
            'total_journals': today_info['journals'],
            'total_articles_sum': today_info['articles_sum'],
            'paper': today_info['paper'], # ALL data
            'is_first_page': True
        }
        full_html = self._generate_html(full_info)
        out_path = os.path.join(os.path.dirname(__file__), '../../output/paper/latest.html')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        print(f"[Paper] Unified full report saved to: {out_path} ({len(full_html)} bytes)")

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
    
    def _load_feeds_from_ini(self):
        """从 default.ini 配置文件加载订阅列表"""
        from core.config import config as core_config
        
        journals = core_config.get_section('paper.journals') or {}
        researchers = core_config.get_section('paper.researchers') or {}
        
        feeds = []
        for title, url in journals.items():
            feeds.append({'title': title, 'url': url, 'type': 'journal'})
        for title, url in researchers.items():
            feeds.append({'title': title, 'url': url, 'type': 'researcher'})
            
        print(f"[Paper] Loaded {len(journals)} journals and {len(researchers)} researchers from INI")
        return feeds

    def _fetch_feed(self, feed_info):
        """抓取单个 RSS 源 (High Availability Mode)"""
        title = feed_info['title']
        url = feed_info['url']
        f_type = feed_info['type']
        
        max_retries = 3
        timeout = 30 # 放宽到 30s
        
        for attempt in range(max_retries):
            try:
                # 简单请求
                resp = requests.get(url, timeout=timeout, headers={
                    'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
                }, proxies={"http": None, "https": None})  # 直连，不走本地代理
                
                if resp.status_code == 200:
                    try:
                        parsed = feedparser.parse(resp.content)
                        # double check parsing success
                        if not parsed.entries and parsed.bozo:
                            # 可能是解析错误，但如果是 200 OK 且无内容，也许多试几次没用，但在 unstable 网络下值得一试
                            # Log warning but don't fail immediately unless it's last attempt
                            if attempt == max_retries - 1:
                                print(f"[Paper] Warning: Empty/Invalid feed from {title} (Bozo: {parsed.bozo_exception})")
                            continue
                            
                        articles = []
                        for entry in parsed.entries:
                            # 转换时间 - 优先 published, 次之 updated
                            dt = None
                            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                                dt = datetime(*entry.published_parsed[:6])
                            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                                dt = datetime(*entry.updated_parsed[:6])
                            
                            if not dt:
                                # 无日期文章：fallback 到最近 12 小时（当做“最近更新”处理）
                                # 不再使用 datetime.min 导致全部被时间过滤器丢弃
                                dt = datetime.now() - timedelta(hours=12)
                            
                            content = ""
                            if hasattr(entry, 'description'): content = entry.description
                            if hasattr(entry, 'summary'): content = entry.summary
                            if hasattr(entry, 'content'): content = entry.content[0].value
                            
                            articles.append({
                                'title': entry.title,
                                'link': entry.link,
                                'datetime': dt,
                                'content': content
                            })
                        
                        # Success!
                        return {'journal': title, 'articles': articles, 'type': f_type}
                    
                    except Exception as e:
                        print(f"[Paper] Parse error for {title}: {e}")
                else:
                    print(f"[Paper] HTTP {resp.status_code} for {title}")
            
            except Exception as e:
                print(f"[Paper] Fetch error for {title} (Attempt {attempt+1}/{max_retries}): {e}")
            
            # Backoff before retry
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
        
        print(f"[Paper] Failed to fetch {title} after {max_retries} attempts.")
        return None
    
    def _include_keywords(self, paper) -> tuple:
        """检查论文是否包含关键词"""
        total_keywords = self.CHN_KEYWORDS + self.ENG_KEYWORDS
        
        # 如果未配置任何关键词，则默认认为“不过滤”，全部通过
        if not total_keywords:
            return True, []
        
        def find_keywords(text, keywords):
            # 使用 re.escape 避免关键词中包含正则特殊字符导致误匹配
            pattern = "|".join(re.escape(k) for k in keywords if k)
            if not pattern:
                return []
            keyword_pattern = re.compile(pattern, re.IGNORECASE)
            return keyword_pattern.findall(text or "")
        
        found_title = find_keywords(paper.get('title', ''), total_keywords)
        found_abstract = find_keywords(paper.get('content', ''), total_keywords)
        
        found_unique = list({i.lower() for i in (found_title + found_abstract)})
        
        has_keyword = bool(found_title or found_abstract)
        return has_keyword, found_unique
    
    def _filter_date(self, paper, journal_title) -> bool:
        """根据时间过滤论文 - 严格 25 小时"""
        _today = datetime.now()
        _dtime = paper['datetime']
        diff = _today - _dtime
        
        # 统一使用 25 小时，不再为 OSA 提供额外容差
        _past_hours = self.PAST_HOURS
        
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
        """获取论文数据 (Dispatcher)"""
        # Always fetch ArXiv and S2 as they are dynamic
        arxiv_list = self._get_data_from_arxiv()
        s2_list = self._get_data_from_s2()

        # 支持环境变量 PAPER_SOURCE_MODE 或 INI 配置 [paper] source = d1
        _source_mode = os.getenv('PAPER_SOURCE_MODE') or config.get('paper', 'source', fallback='rss')
        if _source_mode == 'd1':
            res = self._get_data_from_d1()
        else:
            res = self._get_data_from_rss()
            
        res['arxiv'] = arxiv_list
        res['s2'] = s2_list
        return res

    def _get_data_from_arxiv(self) -> list:
        """从 ArXiv API 获取数据"""
        queries = config.get_section('paper.queries')
        if not queries:
            return []
            
        all_arxiv = []
        now = datetime.now()
        
        for name, query in queries.items():
            self.logger.info(f"[Paper] Searching ArXiv for {name}: {query}")
            try:
                # url = f"http://export.arxiv.org/api/query?search_query={requests.utils.quote(query)}&sortBy=submittedDate&sortOrder=descending&max_results=5"
                # Safer with requests param
                params = {
                    'search_query': query,
                    'sortBy': 'submittedDate',
                    'sortOrder': 'descending',
                    'max_results': 20
                }
                r = requests.get("https://export.arxiv.org/api/query", params=params, timeout=15,
                                 proxies={"http": None, "https": None})  # 直连，不走本地代理
                feed = feedparser.parse(r.text)
                
                for entry in feed.entries:
                    # ArXiv date format: 2024-02-15T00:00:00Z
                    pub_date = entry.published
                    paper = {
                        'title': entry.title.replace('\n', ' ').strip(),
                        'link': entry.link,
                        'author': ", ".join([a.name for a in entry.authors]),
                        'content': entry.summary.replace('\n', ' ').strip(),
                        'journal': f"ArXiv ({name})",
                        'date': pub_date,
                    }
                    
                    # 时间窗口过滤：仅保留最近 PAST_HOURS 内的论文
                    try:
                        dt = datetime.strptime(pub_date, "%Y-%m-%dT%H:%M:%SZ")
                        if now - dt > timedelta(hours=self.PAST_HOURS):
                            continue
                    except Exception:
                        # 日期解析失败时不过度严格过滤，交由后续去重/人工判断
                        pass
                    
                    # 时间窗口内的文章直接收录（每天只运行一次，不需要逐条 D1 去重）
                    all_arxiv.append(paper)
                         
            except Exception as e:
                self.logger.error(f"ArXiv search error ({name}): {e}")
                
        return all_arxiv

    def _get_data_from_s2(self) -> list:
        """从 Semantic Scholar 获取学者动态"""
        authors = config.get_section('paper.authors')
        if not authors:
            return []
            
        all_s2 = []
        for name, author_id in authors.items():
            self.logger.info(f"[Paper] Tracking Scholar {name} (ID: {author_id})")
            try:
                # API: /graph/v1/author/{author_id}/papers
                url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
                params = {'fields': 'title,url,year,publicationDate,authors,abstract', 'limit': 3}
                r = requests.get(url, params=params, timeout=15,
                                 proxies={"http": None, "https": None})  # 直连，不走本地代理
                data = r.json()
                
                if 'data' in data:
                    for p in data['data']:
                        # Filtering by date: Only if publicationDate is recent (within last 30 days for scholarship)
                        # Or if we haven't seen it
                        pub_date = p.get('publicationDate') or f"{p.get('year')}-01-01"
                        
                        art = {
                            'title': p['title'],
                            'link': p['url'],
                            'author': ", ".join([a['name'] for a in p.get('authors', [])]),
                            'content': p.get('abstract') or "(无摘要)",
                            'journal': f"Scholar: {name}",
                            'date': pub_date
                        }
                        
                        # 直接收录（无需逐条 D1 去重）
                        all_s2.append(art)
            except Exception as e:
                 self.logger.error(f"S2 search error ({name}): {e}")
        return all_s2

    def _is_new_paper(self, paper: dict) -> bool:
        """通过 D1 检查是否是新论文"""
        # Unique ID for paper: link or title
        pid = paper.get('link') or paper.get('title')
        if not pid: return True
        
        # Check cloud cache (D1 Client)
        from core.d1_client import D1Client
        d1 = D1Client()
        if not d1.enabled:
            return True # Fail open if DB not enabled
            
        # Table paper_seen_ids: key, updated_at
        try:
            d1.ensure_table('sys_kv', "") 
            res = d1.query("SELECT value FROM sys_kv WHERE key = ?", [f"paper_seen_{pid}"])
            if res['success'] and res['data'] and res['data'][0]['results']:
                return False # Seen
            
            # Not seen, save it
            d1.query("INSERT OR REPLACE INTO sys_kv (key, value, updated_at) VALUES (?, ?, datetime('now'))", 
                     [f"paper_seen_{pid}", "1"])
            return True
        except Exception as e:
            print(f"[Paper] Cache check failed: {e}")
            return True
        
        # Local fallback if D1 disabled
        return True

    def _get_data_from_d1(self) -> dict:
        """从 D1 数据库获取数据"""
        from core.d1_client import D1Client
        d1 = D1Client()
        if not d1.enabled:
            print("[Paper] D1 is disabled. Falling back to RSS.")
            return self._get_data_from_rss()
            
        limit = int(os.getenv('PAPER_ARTICLE_LIMIT', 0))
        limit_clause = f" LIMIT {limit}" if limit > 0 else ""
        sql = f"SELECT * FROM articles WHERE created_at > datetime('now', '-{self.PAST_HOURS} hours') ORDER BY created_at DESC{limit_clause}"
        res = d1.query(sql)
        if not res.get('success'):
            print(f"[Paper] D1 Query failed: {res.get('error')}")
            return self._get_data_from_rss()
            
        rows = res.get('data', [])
        real_rows = []
        if rows and isinstance(rows, list) and len(rows) > 0:
            if 'results' in rows[0]:
                real_rows = rows[0]['results']
            else:
                real_rows = rows
        
        print(f"[Paper] D1 returned {len(real_rows)} raw articles (based on created_at).")
        if not real_rows:
            return {"journals": 0, "today": datetime.now().strftime("%Y-%m-%d"), 
                    "articles_sum": 0, "journals_title": [], "paper": []}

        grouped = {} 
        
        def smart_title(s):
            """Smart Title Case: IEEE, OSA, and small words."""
            if not s: return ""
            # Special acronyms to force uppercase
            uppers = {'ieee', 'osa', 'usa', 'led', 'uv'}
            # Small words to keep lowercase (unless first/last)
            smalls = {'a', 'an', 'the', 'and', 'but', 'or', 'for', 'nor', 'on', 'at', 'to', 'from', 'by', 'with', 'of', 'in'}
            
            words = s.split()
            new_words = []
            for i, w in enumerate(words):
                clean_w = w.lower()
                # Remove common punctuation for check (e.g., "Co.,") - Keep simple for now
                if clean_w in uppers:
                    new_words.append(clean_w.upper())
                elif i > 0 and i < len(words) - 1 and clean_w in smalls:
                    new_words.append(clean_w)
                else:
                    new_words.append(w.capitalize())
            return " ".join(new_words)

        for row in real_rows:
            # Format Journal Name
            raw_j_name = row.get('source_name', 'Unknown')
            j_name = smart_title(raw_j_name)
            
            j_type = row.get('source_type', 'journal')
            if j_name not in grouped: grouped[j_name] = {'type': j_type, 'data': []}
                
            art = {
                'title': row.get('title'),
                'link': row.get('link'),
                'datetime': datetime.strptime(row.get('published_at'), '%Y-%m-%d %H:%M:%S') if row.get('published_at') else datetime.now(),
                'content': row.get('content', ''),
                'id': row.get('id')
            }
            
            art['is_include_keyword'], art['keywords'] = self._include_keywords(art)
            # 只有 GENERAL_JOURNALS 中的期刊才需要强制关键词命中
            # D1 模式已通过 SQL created_at 时间窗口过滤，无需再用 published_at 二次过滤
            j_name_lower = j_name.lower()
            in_general = any(j_name_lower == g.lower() for g in self.GENERAL_JOURNALS)
            if j_type == 'journal' and in_general and not art['is_include_keyword']:
                continue
            
            if self.llm_provider and (art['is_include_keyword'] or self.test_mode):
                try:
                    clean_text = re.sub(r'<[^>]+>', '', art['content']).strip()
                    txt_input = f"Title: {art['title']}\\nAbstract: {clean_text[:2000]}"
                    art['summary'] = self.llm_provider.summarize(txt_input)
                except: pass
            
            grouped[j_name]['data'].append(art)
            
        final_paper_data = []
        total_articles_sum = 0
        for j_name, info in grouped.items():
            if not info['data']: continue
            top_n = info['data'][:self.MAX_ARTICLES_PER_JOURNAL]
            final_paper_data.append({
                "journal": j_name, "data": top_n,
                "articles_nu": len(top_n), "type": info['type']
            })
            total_articles_sum += len(top_n)

        final_paper_data.sort(key=lambda x: (0 if x['type'] == 'researcher' else 1, x['journal']))
        return {
            "journals": len(final_paper_data),
            "today": datetime.now().strftime("%Y-%m-%d"),
            "articles_sum": total_articles_sum,
            "journals_title": [p['journal'] for p in final_paper_data],
            "paper": final_paper_data
        }

    def _get_data_from_rss(self) -> dict:
        """获取论文数据 - INI 抓取版"""
        feeds_info = self._load_feeds_from_ini()
        if not feeds_info:
            return {"journals": 0, "today": datetime.now().strftime("%Y-%m-%d"), 
                    "articles_sum": 0, "journals_title": [], "paper": []}

        # 并行抓取加速
        print(f"[Paper] Starting parallel fetch for {len(feeds_info)} feeds...")
        final_paper_data = []
        total_articles_sum = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            future_to_feed = {executor.submit(self._fetch_feed, f): f for f in feeds_info}
            for future in concurrent.futures.as_completed(future_to_feed):
                res = future.result()
                if not res: continue
                
                journal_title = res['journal']
                raw_articles = res['articles']
                f_type = res.get('type', 'journal')
                
                # 限流：每个期刊超过最大数量则截断
                raw_articles = raw_articles[:self.MAX_ARTICLES_PER_JOURNAL]
                
                # 过滤逻辑
                filtered_list = []
                ino = 1
                for art in raw_articles:
                    # 1. 时间过滤
                    if not self._filter_date(art, journal_title):
                        continue
                    
                    # 2. 关键词检测
                    art['is_include_keyword'], art['keywords'] = self._include_keywords(art)
                    
                    # 3. 期刊筛选逻辑 (通用期刊必须包含关键词)
                    # 研究人员订阅 (researcher) 通常不强制要求关键词
                    if f_type == 'journal' and journal_title.lower() in self._general_journals_lower and not art['is_include_keyword']:
                        continue
                    
                    # 4. LLM 摘要 (如果有)
                    if self.llm_provider and (art['is_include_keyword'] or self.test_mode):
                        try:
                            clean_text = re.sub(r'<[^>]+>', '', art['content']).strip()
                            txt_input = f"Title: {art['title']}\nAbstract: {clean_text[:2000]}"
                            art['summary'] = self.llm_provider.summarize(txt_input)
                        except: pass
                    
                    art['id'] = ino
                    filtered_list.append(art)
                    ino += 1
                
                if filtered_list:
                    final_paper_data.append({
                        "journal": journal_title,
                        "data": filtered_list,
                        "articles_nu": len(filtered_list),
                        "type": f_type
                    })
                    total_articles_sum += len(filtered_list)

        # 排序：研究人员在前，期刊在后
        final_paper_data.sort(key=lambda x: (0 if x['type'] == 'researcher' else 1, x['journal']))

        return {
            "journals": len(final_paper_data),
            "today": datetime.now().strftime("%Y-%m-%d"),
            "articles_sum": total_articles_sum,
            "journals_title": [p['journal'] for p in final_paper_data],
            "paper": final_paper_data
        }

    def _generate_html(self, today_info) -> str:
        """使用 Jinja2 模板生成 HTML 内容"""
        from jinja2 import Environment, FileSystemLoader
        
        # 加载模板
        template_dir = os.path.join(os.path.dirname(__file__), '../../templates')
        env = Environment(loader=FileSystemLoader(template_dir))
        
        try:
            template = env.get_template('paper.html')
        except Exception as e:
            print(f"[Paper] Warning: Cannot load paper.html template: {e}")
            return self._generate_html_legacy(today_info)
        
        # 准备渲染内容
        context = {
            'today': today_info.get('today'),
            'update_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            'is_first_page': today_info.get('is_first_page', True),
            'total_journals': today_info.get('total_journals') or today_info.get('journals', 0),
            'total_articles_sum': today_info.get('total_articles_sum') or today_info.get('articles_sum', 0),
            'paper': today_info.get('paper', []),
            'in_docker': self.in_docker
        }
        
        return template.render(**context)

    def _generate_html_legacy(self, today_info) -> str:
        """简易版 HTML 生成（备用）"""
        return f"<h3>Paper Report - {today_info.get('today')}</h3><p>Total: {today_info.get('articles_sum')} articles.</p>"


if __name__ == '__main__':
    # 独立测试
    source = PaperSource(topic='me')
    msg = source.run()
    print(f"Title: {msg.title}")
    print(f"Type: {msg.type}")
    print(f"Content length: {len(msg.content)} chars")
    print(f"Metadata: {msg.metadata}")
