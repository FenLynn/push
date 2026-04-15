"""
Paper Source - 学术论文推送
整合原 paper/main.py 的所有功能，适配 IFTTT 架构
"""
import sys
import os
import re
import json
import hashlib
import html as html_lib
import time
import copy
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode
from datetime import datetime, timedelta, timezone
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

    PUSH_SEEN_TABLE = 'paper_push_seen'
    PUSH_AUDIT_DIR = os.path.join(os.path.dirname(__file__), '../../output/paper/audit')
    DEDUPE_QUERY_PARAM_BLOCKLIST = {
        'utm_source', 'utm_medium', 'utm_campaign', 'utm_term', 'utm_content',
        'gclid', 'fbclid', 'mc_cid', 'mc_eid', 'ref', 'source'
    }
    DOI_PATTERN = re.compile(r'(10\.\d{4,9}/[-._;()/:A-Z0-9]+)', re.IGNORECASE)
    LONG_ASCII_TOKEN_RE = re.compile(r'[A-Za-z][A-Za-z0-9]{11,}')
    MIN_JOURNAL_ARTICLES_AT_PAGE_START = 2
    LEGACY_FINALIZE_DELAY_MINUTES = max(5, int(os.getenv('PAPER_LEGACY_FINALIZE_DELAY_MINUTES', '30') or '30'))
    TITLE_SOFT_BREAK_INTERVAL = 10
    
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
    MAX_PAGE_SIZE = 19800  # PushPlus 限制 20000，留 200 chars 安全余量
    TTRSS_CAT_ID = None
    PAST_HOURS = int(os.getenv('PAPER_PAST_HOURS', 25))
    
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
        self._pending_seen_records = []
        self._run_audit = {
            'startedAt': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
            'sourceMode': '',
            'rawRows': 0,
            'includedArticles': 0,
            'includedJournals': 0,
            'inflightRowsSkipped': 0,
            'skippedSeen': 0,
            'skippedDuplicateRows': 0,
            'skippedKeyword': 0,
            'seenExamples': [],
            'duplicateExamples': [],
            'keywordExamples': [],
            'pendingSeen': 0,
        }
        
        # Docker 环境自适应
        self.in_docker = self._is_docker()
        if self.in_docker:
            print("[Paper] Running in DOCKER environment")
        
        # Initialize Keywords from Config
        self._load_keywords()
        
        # Paper 摘要默认关闭，避免 push 主流程依赖外部 LLM 可用性。
        self.paper_llm_enabled = self._is_truthy(os.getenv('PAPER_ENABLE_LLM', config.get('paper', 'enable_llm', fallback='false')))
        if self.paper_llm_enabled:
            llm_conf = config.get_llm_config()
            self.llm_provider = LLMFactory.create_provider(llm_conf)
            if self.llm_provider:
                print(f"[Paper] LLM Provider Initialized: {llm_conf.get('provider')}")
            else:
                print("[Paper] LLM Provider NOT initialized")
        else:
            self.llm_provider = None
            print("[Paper] LLM summaries disabled")
            
        # Normalize GENERAL_JOURNALS for case-insensitive check
        self._general_journals_lower = [j.lower() for j in self.GENERAL_JOURNALS]

    def _append_audit_example(self, key: str, payload: dict, limit: int = 12):
        items = self._run_audit.setdefault(key, [])
        if len(items) < limit:
            items.append(payload)

    @staticmethod
    def _is_truthy(value) -> bool:
        return str(value or '').strip().lower() in {'1', 'true', 'yes', 'on'}

    def _write_run_audit(self):
        self._run_audit['finishedAt'] = datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S')
        self._run_audit['pendingSeen'] = len(self._pending_seen_records)

        try:
            out_dir = os.path.normpath(self.PUSH_AUDIT_DIR)
            os.makedirs(out_dir, exist_ok=True)
            stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            latest_path = os.path.join(out_dir, 'latest_run.json')
            archive_path = os.path.join(out_dir, f'run_{stamp}.json')
            payload = json.dumps(self._run_audit, ensure_ascii=False, indent=2)
            with open(latest_path, 'w', encoding='utf-8') as file_obj:
                file_obj.write(payload)
            with open(archive_path, 'w', encoding='utf-8') as file_obj:
                file_obj.write(payload)
            self.logger.info('Paper audit written: %s', archive_path)
        except Exception as exc:
            self.logger.warning('Failed to write paper audit: %s', exc)

    def _extract_doi_from_article(self, article: dict) -> str:
        for candidate in (
            article.get('doi'),
            article.get('link'),
            article.get('content'),
            article.get('title'),
        ):
            match = self.DOI_PATTERN.search(str(candidate or ''))
            if match:
                return match.group(1).rstrip(').,;]').upper()
        return ''

    def _normalize_link_for_dedupe(self, link: str) -> str:
        raw_link = str(link or '').strip()
        if not raw_link:
            return ''

        try:
            parts = urlsplit(raw_link)
            filtered_query = []
            for key, value in parse_qsl(parts.query, keep_blank_values=True):
                if key.lower() in self.DEDUPE_QUERY_PARAM_BLOCKLIST:
                    continue
                filtered_query.append((key, value))
            normalized = urlunsplit((
                parts.scheme.lower(),
                parts.netloc.lower(),
                parts.path.rstrip('/'),
                urlencode(filtered_query, doseq=True),
                ''
            ))
            return normalized.strip()
        except Exception:
            return raw_link

    def _normalize_title_for_dedupe(self, title: str) -> str:
        text = re.sub(r'<[^>]+>', ' ', str(title or ''))
        text = text.replace('—', '-').replace('–', '-')
        text = re.sub(r'\s+', ' ', text).strip().lower()
        return text

    def _dedupe_keywords(self, keywords: list) -> list:
        ordered = []
        seen = set()
        for keyword in sorted((str(item or '').strip() for item in keywords or [] if str(item or '').strip()), key=lambda item: (-len(item), item.lower())):
            token = keyword.lower()
            if token in seen:
                continue
            seen.add(token)
            ordered.append(keyword)
        return ordered

    def _find_keywords(self, text: str, keywords: list) -> list:
        ordered_keywords = self._dedupe_keywords(keywords)
        if not ordered_keywords:
            return []

        pattern = re.compile('|'.join(re.escape(keyword) for keyword in ordered_keywords), re.IGNORECASE)
        found = []
        seen = set()
        for match in pattern.finditer(text or ''):
            token = match.group(0).strip()
            key = token.lower()
            if not token or key in seen:
                continue
            seen.add(key)
            found.append(token)
        return found

    def _analyze_keywords(self, paper) -> dict:
        total_keywords = self.CHN_KEYWORDS + self.ENG_KEYWORDS
        if not total_keywords:
            return {
                'has_keyword': True,
                'all': [],
                'title': [],
                'abstract_only': [],
            }

        title_text = str(paper.get('title') or '')
        abstract_text = re.sub(r'<[^>]+>', ' ', str(paper.get('content') or ''))
        found_title = self._find_keywords(title_text, total_keywords)
        found_abstract = self._find_keywords(abstract_text, total_keywords)

        found_all = []
        seen = set()
        for item in found_title + found_abstract:
            token = item.lower()
            if token in seen:
                continue
            seen.add(token)
            found_all.append(item)

        title_tokens = {item.lower() for item in found_title}
        abstract_only = [item for item in found_all if item.lower() not in title_tokens]
        return {
            'has_keyword': bool(found_all),
            'all': found_all,
            'title': found_title,
            'abstract_only': abstract_only,
        }

    def _render_title_keyword_html(self, title: str, title_keywords: list) -> str:
        raw_title = str(title or '').strip()
        if not raw_title:
            return '--'

        keyword_hits = self._dedupe_keywords(title_keywords)
        pattern = re.compile('|'.join(re.escape(keyword) for keyword in keyword_hits), re.IGNORECASE) if keyword_hits else None
        allowed_tags = {'sub', 'sup', 'i', 'em', 'b', 'strong'}
        rendered = []

        for part in re.split(r'(<[^>]+>)', raw_title):
            if not part:
                continue

            if part.startswith('<') and part.endswith('>'):
                match = re.match(r'^<\s*(/?)\s*([a-zA-Z0-9]+)[^>]*>$', part)
                if match and match.group(2).lower() in allowed_tags:
                    slash = '/' if match.group(1) else ''
                    rendered.append(f'<{slash}{match.group(2).lower()}>')
                else:
                    rendered.append(html_lib.escape(part))
                continue

            text = html_lib.unescape(part)
            if not pattern:
                rendered.append(html_lib.escape(text))
                continue

            last_index = 0
            for hit in pattern.finditer(text):
                start, end = hit.span()
                if start > last_index:
                    rendered.append(html_lib.escape(text[last_index:start]))
                rendered.append(f'<span class="kh">{html_lib.escape(hit.group(0))}</span>')
                last_index = end

            if last_index < len(text):
                rendered.append(html_lib.escape(text[last_index:]))

        title_html = ''.join(rendered) or html_lib.escape(html_lib.unescape(raw_title))
        return self._apply_title_soft_breaks(title_html)

    def _insert_soft_hyphens(self, text: str) -> str:
        def replace(match):
            token = match.group(0)
            if len(token) <= self.TITLE_SOFT_BREAK_INTERVAL + 2:
                return token

            pieces = [token[idx:idx + self.TITLE_SOFT_BREAK_INTERVAL] for idx in range(0, len(token), self.TITLE_SOFT_BREAK_INTERVAL)]
            return '&shy;'.join(pieces)

        return self.LONG_ASCII_TOKEN_RE.sub(replace, text)

    def _apply_title_soft_breaks(self, title_html: str) -> str:
        if not title_html:
            return title_html

        rendered = []
        for part in re.split(r'(<[^>]+>)', title_html):
            if not part:
                continue

            if part.startswith('<') and part.endswith('>'):
                rendered.append(part)
                continue

            for chunk in re.split(r'(&[#A-Za-z0-9]+;)', part):
                if not chunk:
                    continue
                if re.fullmatch(r'&[#A-Za-z0-9]+;', chunk):
                    rendered.append(chunk)
                    continue

                chunk = re.sub(r'(?<=[/\-+_])(?=[A-Za-z0-9])', '&#8203;', chunk)
                rendered.append(self._insert_soft_hyphens(chunk))

        return ''.join(rendered)

    def _decorate_keyword_rendering(self, article: dict):
        keyword_info = self._analyze_keywords(article)
        article['is_include_keyword'] = keyword_info['has_keyword']
        article['keywords'] = keyword_info['all']
        article['display_keywords'] = keyword_info['abstract_only']
        article['title_html'] = self._render_title_keyword_html(article.get('title', ''), keyword_info['title'])

    def _build_push_dedupe_identity(self, article: dict, source_name: str) -> dict:
        doi = self._extract_doi_from_article(article)
        title_norm = self._normalize_title_for_dedupe(article.get('title', ''))
        source_norm = self._normalize_title_for_dedupe(source_name)
        link_norm = self._normalize_link_for_dedupe(article.get('link', ''))

        if source_norm and title_norm:
            raw_key = f'title|{source_norm}|{title_norm}'
            kind = 'title'
        elif doi:
            raw_key = f'doi|{doi}'
            kind = 'doi'
        elif link_norm:
            raw_key = f'link|{link_norm}'
            kind = 'link'
        else:
            raw_key = f'fallback|{source_norm}|{title_norm}|{article.get("link", "")}'
            kind = 'fallback'

        digest = hashlib.sha256(raw_key.encode('utf-8')).hexdigest()
        return {
            'dedupe_key': f'{kind}:{digest}',
            'dedupe_kind': kind,
            'title': str(article.get('title') or '').strip(),
            'link': str(article.get('link') or '').strip(),
            'doi': doi,
            'source_name': str(source_name or '').strip(),
            'published_at': str(article.get('published_at') or '').strip(),
            'created_at': str(article.get('created_at') or '').strip(),
        }

    def _ensure_push_seen_table(self, d1):
        schema = f"""
        CREATE TABLE IF NOT EXISTS {self.PUSH_SEEN_TABLE} (
            dedupe_key TEXT PRIMARY KEY,
            dedupe_kind TEXT,
            source_name TEXT,
            title TEXT,
            link TEXT,
            doi TEXT,
            published_at TEXT,
            first_seen_created_at TEXT,
            first_pushed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            last_pushed_at TEXT DEFAULT CURRENT_TIMESTAMP,
            push_count INTEGER DEFAULT 1,
            updated_at TEXT DEFAULT CURRENT_TIMESTAMP
        );
        CREATE INDEX IF NOT EXISTS idx_paper_push_seen_last ON {self.PUSH_SEEN_TABLE}(last_pushed_at);
        CREATE INDEX IF NOT EXISTS idx_paper_push_seen_source ON {self.PUSH_SEEN_TABLE}(source_name, last_pushed_at);
        """
        d1.ensure_table(self.PUSH_SEEN_TABLE, schema)

    def _fetch_seen_push_keys(self, d1, identities: list) -> set:
        keys = [item['dedupe_key'] for item in identities if item.get('dedupe_key')]
        if not keys:
            return set()

        seen_keys = set()
        chunk_size = 80
        for start in range(0, len(keys), chunk_size):
            batch = keys[start:start + chunk_size]
            placeholders = ','.join('?' for _ in batch)
            sql = f"SELECT dedupe_key FROM {self.PUSH_SEEN_TABLE} WHERE dedupe_key IN ({placeholders})"
            res = d1.query(sql, batch)
            if not res.get('success'):
                self.logger.warning('Failed to fetch paper seen keys: %s', res.get('error'))
                return set()

            rows = res.get('data', [])
            results = rows[0].get('results', []) if rows and isinstance(rows[0], dict) else []
            seen_keys.update(str(item.get('dedupe_key') or '').strip() for item in results if item.get('dedupe_key'))

        return seen_keys

    def _ensure_article_batch_columns(self, d1):
        res = d1.query("PRAGMA table_info(articles)")
        rows = res.get('data', []) if res.get('success') else []
        results = rows[0].get('results', []) if rows and isinstance(rows[0], dict) else []
        existing = {str(item.get('name') or '').strip().lower() for item in results}
        for column_name, column_type in {
            'ingest_batch_id': 'TEXT',
            'ingest_finalized_at': 'TEXT',
            'first_seen_at': 'TEXT',
            'last_seen_at': 'TEXT',
        }.items():
            if column_name in existing:
                continue
            d1.query(f"ALTER TABLE articles ADD COLUMN {column_name} {column_type}")

        d1.query("CREATE INDEX IF NOT EXISTS idx_articles_ingest_finalized ON articles(ingest_finalized_at)")
        d1.query("CREATE INDEX IF NOT EXISTS idx_articles_ingest_batch ON articles(ingest_batch_id)")
        d1.query("CREATE INDEX IF NOT EXISTS idx_articles_first_seen ON articles(first_seen_at)")
        d1.query("CREATE INDEX IF NOT EXISTS idx_articles_last_seen ON articles(last_seen_at)")

    def _backfill_legacy_article_finalization(self, d1):
        cutoff = f'-{self.LEGACY_FINALIZE_DELAY_MINUTES} minutes'
        d1.query(
            """
            UPDATE articles
            SET ingest_batch_id = COALESCE(NULLIF(ingest_batch_id, ''), 'legacy'),
                ingest_finalized_at = COALESCE(NULLIF(ingest_finalized_at, ''), created_at),
                first_seen_at = COALESCE(NULLIF(first_seen_at, ''), created_at),
                last_seen_at = COALESCE(NULLIF(last_seen_at, ''), created_at)
            WHERE COALESCE(ingest_finalized_at, '') = ''
              AND datetime(created_at) <= datetime('now', ?)
            """,
            [cutoff],
        )

    def _build_d1_article_sql(self, limit: int = 0) -> str:
        limit_clause = f" LIMIT {limit}" if limit > 0 else ""
        return (
            f"SELECT * FROM articles WHERE datetime(COALESCE(NULLIF(first_seen_at, ''), created_at)) > datetime('now', '-{self.PAST_HOURS} hours') "
            "AND COALESCE(ingest_finalized_at, '') != '' ORDER BY datetime(COALESCE(NULLIF(first_seen_at, ''), created_at)) DESC, datetime(created_at) DESC"
            f"{limit_clause}"
        )

    def _count_inflight_rows(self, d1) -> int:
        sql = f"SELECT COUNT(*) AS cnt FROM articles WHERE datetime(COALESCE(NULLIF(first_seen_at, ''), created_at)) > datetime('now', '-{self.PAST_HOURS} hours') AND COALESCE(ingest_finalized_at, '') = ''"
        res = d1.query(sql)
        if not res.get('success'):
            return 0
        rows = res.get('data', [])
        results = rows[0].get('results', []) if rows and isinstance(rows[0], dict) else []
        return int((results[0] if results else {}).get('cnt', 0) or 0)

    def _rank_window_row(self, row: dict) -> tuple:
        return (
            1 if str(row.get('doi') or '').strip() else 0,
            1 if str(row.get('authors') or '').strip() else 0,
            len(str(row.get('content') or '')),
            str(row.get('last_seen_at') or row.get('created_at') or '').strip(),
            str(row.get('created_at') or '').strip(),
        )

    def _dedupe_current_window_rows(self, rows: list) -> list:
        deduped = {}
        for row in rows:
            identity = self._build_push_dedupe_identity({
                'title': row.get('title'),
                'link': row.get('link'),
                'content': row.get('content', ''),
                'published_at': row.get('published_at') or '',
                'created_at': row.get('created_at') or '',
                'doi': row.get('doi') or '',
            }, row.get('source_name', 'Unknown'))
            current = deduped.get(identity['dedupe_key'])
            if current is not None:
                self._run_audit['skippedDuplicateRows'] += 1
                self._append_audit_example('duplicateExamples', {
                    'source': row.get('source_name'),
                    'title': row.get('title'),
                    'createdAt': row.get('created_at'),
                    'publishedAt': row.get('published_at'),
                    'dedupeKind': identity['dedupe_kind'],
                })
                if self._rank_window_row(row) <= self._rank_window_row(current['row']):
                    continue

            deduped[identity['dedupe_key']] = {'row': row, 'identity': identity}

        return sorted(
            deduped.values(),
            key=lambda item: (
                str(item['row'].get('first_seen_at') or item['row'].get('created_at') or '').strip(),
                str(item['row'].get('created_at') or '').strip(),
            ),
            reverse=True,
        )

    def after_send_success(self):
        if not self._pending_seen_records:
            return

        from core.d1_client import D1Client
        d1 = D1Client()
        if not d1.enabled:
            self.logger.warning('Skip persisting paper seen ledger because D1 is disabled.')
            self._pending_seen_records = []
            return

        self._ensure_push_seen_table(d1)
        now_text = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        success = 0

        unique_records = {}
        for item in self._pending_seen_records:
            dedupe_key = item.get('dedupe_key')
            if dedupe_key and dedupe_key not in unique_records:
                unique_records[dedupe_key] = item

        for item in unique_records.values():
            sql = f"""
            INSERT INTO {self.PUSH_SEEN_TABLE}
            (dedupe_key, dedupe_kind, source_name, title, link, doi, published_at, first_seen_created_at, first_pushed_at, last_pushed_at, push_count, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            ON CONFLICT(dedupe_key) DO UPDATE SET
                dedupe_kind = excluded.dedupe_kind,
                source_name = COALESCE(NULLIF(excluded.source_name, ''), {self.PUSH_SEEN_TABLE}.source_name),
                title = COALESCE(NULLIF(excluded.title, ''), {self.PUSH_SEEN_TABLE}.title),
                link = COALESCE(NULLIF(excluded.link, ''), {self.PUSH_SEEN_TABLE}.link),
                doi = COALESCE(NULLIF(excluded.doi, ''), {self.PUSH_SEEN_TABLE}.doi),
                published_at = COALESCE(NULLIF(excluded.published_at, ''), {self.PUSH_SEEN_TABLE}.published_at),
                last_pushed_at = excluded.last_pushed_at,
                push_count = {self.PUSH_SEEN_TABLE}.push_count + 1,
                updated_at = excluded.updated_at
            """
            params = [
                item['dedupe_key'], item['dedupe_kind'], item['source_name'], item['title'], item['link'],
                item['doi'], item['published_at'], item['created_at'], now_text, now_text, now_text
            ]
            res = d1.query(sql, params)
            if res.get('success'):
                success += 1
            else:
                self.logger.warning('Failed to persist paper seen ledger for %s: %s', item['title'], res.get('error'))

        self.logger.info('Paper seen ledger persisted: %s/%s', success, len(unique_records))
        self._pending_seen_records = []

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

    def _estimate_article_window_size(self, articles: list, count: int) -> int:
        return sum(self._estimate_article_size(article) for article in articles[:count])
    

    def _estimate_article_size(self, article: dict) -> int:
        """估算单篇文章渲染后的 HTML 字符大小
        
        注意：只计算模板中实际会渲染的字段。
        content/abstract 字段不在模板中显示（除非有 LLM summary），不能计入。
        """
        size = len(article.get('title', ''))   # 标题（显示）
        size += len(article.get('link', ''))   # 链接（显示）
        # 关键词标签（仅命中时显示）
        kws = article.get('display_keywords') or article.get('keywords', [])
        if kws:
            size += sum(len(k) + 40 for k in kws)  # 每个 tag 约 40 chars HTML
        # LLM 摘要（仅有 summary 时显示）
        if article.get('summary'):
            size += len(article['summary']) + 60
        return size + 110  # 固定 HTML 标签开销（div.ar/div.ac/span.ix/a.lk 等）

    def _clone_page_papers(self, page_papers: list) -> list:
        cloned = []
        for feed in page_papers or []:
            articles = list(feed.get('data') or [])
            if not articles:
                continue
            cloned.append({
                'journal': feed['journal'],
                'data': articles,
                'articles_nu': len(articles),
            })
        return cloned

    def _build_page_info(self, today_info: dict, page_papers: list, *, current_page: int = 1,
                         total_pages: int = 1, is_first_page: bool = True, full_report: bool = False) -> dict:
        return {
            'today': today_info['today'],
            'is_first_page': is_first_page,
            'current_page': current_page,
            'total_pages': total_pages,
            'full_report': full_report,
            'total_journals': today_info['journals'],
            'total_articles_sum': today_info['articles_sum'],
            'paper': page_papers,
        }

    def _render_page_length(self, today_info: dict, page_papers: list) -> int:
        if not page_papers:
            return 0
        probe_info = self._build_page_info(
            today_info,
            page_papers,
            current_page=8,
            total_pages=8,
            is_first_page=False,
            full_report=False,
        )
        return len(self._generate_html(probe_info))

    def _split_page_by_render_length(self, today_info: dict, page_papers: list) -> list:
        normalized_page = self._clone_page_papers(page_papers)
        if not normalized_page:
            return []

        split_pages = []
        current_page = []

        for feed in normalized_page:
            journal = feed['journal']
            for article in feed['data']:
                candidate_page = self._clone_page_papers(current_page)
                if candidate_page and candidate_page[-1]['journal'] == journal:
                    candidate_page[-1]['data'].append(article)
                    candidate_page[-1]['articles_nu'] = len(candidate_page[-1]['data'])
                else:
                    candidate_page.append({
                        'journal': journal,
                        'data': [article],
                        'articles_nu': 1,
                    })

                candidate_length = self._render_page_length(today_info, candidate_page)
                if candidate_length <= self.MAX_PAGE_SIZE or not current_page:
                    current_page = candidate_page
                    continue

                split_pages.append(current_page)
                current_page = [{
                    'journal': journal,
                    'data': [article],
                    'articles_nu': 1,
                }]

                single_length = self._render_page_length(today_info, current_page)
                if single_length > self.MAX_PAGE_SIZE:
                    self.logger.warning(
                        "Paper single-article page still exceeds limit (%s chars): %s",
                        single_length,
                        str(article.get('title', '') or '')[:120],
                    )

        if current_page:
            split_pages.append(current_page)

        return split_pages

    def run(self) -> list:
        """运行获取流程并返回消息列表"""
        self._pending_seen_records = []
        self._run_audit.update({
            'startedAt': datetime.now(timezone(timedelta(hours=8))).strftime('%Y-%m-%d %H:%M:%S'),
            'includedArticles': 0,
            'includedJournals': 0,
            'inflightRowsSkipped': 0,
            'skippedSeen': 0,
            'skippedDuplicateRows': 0,
            'skippedKeyword': 0,
            'seenExamples': [],
            'duplicateExamples': [],
            'keywordExamples': [],
            'pendingSeen': 0,
        })
        today_info = self._get_data()
        # Remove early return to allow "No Update" message generation
            
        # ── 分页逻辑 ─────────────────────────────────────────────────────────
        # TEMPLATE_OVERHEAD: CSS(~1500) + banner/footer(~500) + 缓冲
        # 注意：每个期刊标题行约 180 chars，也必须算入，否则实际 HTML > PushPlus 20000 限制
        TEMPLATE_OVERHEAD = 2000
        JOURNAL_HEADER_COST = 180   # <div class="jg"><div class="jn">...的 HTML 开销
        all_pages = []
        current_papers = []
        current_page_size = TEMPLATE_OVERHEAD  # 从框架开销开始计算

        def settle_page():
            nonlocal current_papers, current_page_size
            if current_papers:
                all_pages.append(current_papers)
                current_papers = []
                current_page_size = TEMPLATE_OVERHEAD

        for feed in today_info['paper']:
            articles = feed['data']
            if not articles:
                continue

            journal_articles_to_page = []
            for art_idx, art in enumerate(articles):
                remaining_articles = articles[art_idx:]
                if not journal_articles_to_page and current_papers and len(remaining_articles) >= self.MIN_JOURNAL_ARTICLES_AT_PAGE_START:
                    preview_count = min(self.MIN_JOURNAL_ARTICLES_AT_PAGE_START, len(remaining_articles))
                    preview_cost = JOURNAL_HEADER_COST + self._estimate_article_window_size(remaining_articles, preview_count)
                    if current_page_size + preview_cost > self.MAX_PAGE_SIZE:
                        settle_page()

                est_size = self._estimate_article_size(art)
                # 新期刊的第一篇需要额外计算期刊标题行开销
                is_first_of_journal = not journal_articles_to_page
                header_cost = JOURNAL_HEADER_COST if is_first_of_journal else 0

                if current_page_size + header_cost + est_size > self.MAX_PAGE_SIZE:
                    if journal_articles_to_page:
                        current_papers.append({
                            'journal': feed['journal'],
                            'data': journal_articles_to_page,
                            'articles_nu': len(journal_articles_to_page)
                        })
                        journal_articles_to_page = []
                    settle_page()
                    # 新页上，这个期刊仍需要标题行
                    header_cost = JOURNAL_HEADER_COST

                if not journal_articles_to_page:
                    # 计入本期刊标题行开销（正式开始此期刊在当前页）
                    current_page_size += JOURNAL_HEADER_COST
                journal_articles_to_page.append(art)
                current_page_size += est_size

            if journal_articles_to_page:
                current_papers.append({
                    'journal': feed['journal'],
                    'data': journal_articles_to_page,
                    'articles_nu': len(journal_articles_to_page)
                })

        # ArXiv / S2 优先尝试并入当前未结算页（current_papers）
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
            feed_size = sum(self._estimate_article_size(a) for a in feed['data'])
            if current_page_size + feed_size <= self.MAX_PAGE_SIZE:
                # 并入当前页
                current_papers.append(feed)
                current_page_size += feed_size
            else:
                # 当前页没位置：先结算，再开新页
                settle_page()
                current_papers.append(feed)
                current_page_size = TEMPLATE_OVERHEAD + feed_size

        # 全部期刊和附加源处理完毕，结算最后一页
        settle_page()

        # Update total counts for metadata and UI header
        virtual_journals = (1 if arxiv_data else 0) + (1 if s2_data else 0)
        virtual_articles = len(arxiv_data) + len(s2_data)
        today_info['journals'] += virtual_journals
        today_info['articles_sum'] += virtual_articles

        safe_pages = []
        for page_papers in all_pages:
            normalized_page = self._clone_page_papers(page_papers)
            rendered_length = self._render_page_length(today_info, normalized_page)
            if rendered_length <= self.MAX_PAGE_SIZE:
                safe_pages.append(normalized_page)
                continue

            self.logger.warning(
                "Estimated paper page overflowed after render (%s chars); re-splitting with actual HTML length.",
                rendered_length,
            )
            safe_pages.extend(self._split_page_by_render_length(today_info, normalized_page))

        all_pages = safe_pages

        base_title = f'学术文献{time.strftime("%m-%d", time.localtime())}'

        # 如果无任何更新，推送一条提醒消息
        if not all_pages:
            html_content = f"""
            <div style="padding: 30px; text-align: center; background-color: #f9fafb; border-radius: 12px; border: 1px solid #e5e7eb; margin: 20px;">
                <p style="font-size: 18px; color: #374151; font-weight: bold; margin-bottom: 10px;">今日无最新论文更新</p>
                <p style="font-size: 14px; color: #6b7280;">由于所监测的 RSS 源在过去 {self.PAST_HOURS} 小时内未发布新文章，或未命中您的关键词，因此今日无摘要生成。</p>
            </div>
            """
            self._run_audit['includedArticles'] = 0
            self._run_audit['includedJournals'] = 0
            self._write_run_audit()
            return [Message(
                title=base_title,
                content=html_content,
                type=ContentType.HTML,
                tags=['paper', 'academic', self.topic],
                metadata={'date': today_info['today'], 'count': 0, 'disable_split': True}
            )]

        # 注：split_oversized_pages 已移除（会导致分割页丢失CSS）
        # 估算已修正为只统计渲染字段，精度足够

        # 生成消息列表
        messages = []
        global_idx = 1       # 文章全局序号（跨页连续）
        journal_page_tracker = {}  # j_name -> 当前出现次数

        # 预先计算每个期刊在总分页中出现的次数（跨页被拆分时需要分卷标签）
        journal_total_pages = {}
        for pg in all_pages:
            for f in pg:
                journal_total_pages[f['journal']] = journal_total_pages.get(f['journal'], 0) + 1

        # 预分配期刊唯一序号：按首次出现顺序，跨页续篇复用同一序号
        journal_idx_map = {}   # j_name -> 唯一期刊序号
        _jidx = 1
        for pg in all_pages:
            for f in pg:
                if f['journal'] not in journal_idx_map:
                    journal_idx_map[f['journal']] = _jidx
                    _jidx += 1

        total_pages = len(all_pages)
        for idx, page_papers in enumerate(all_pages):
            is_first_page = (idx == 0)

            for f_item in page_papers:
                j_name = f_item['journal']
                count = journal_page_tracker.get(j_name, 0) + 1
                journal_page_tracker[j_name] = count

                # 跨页被拆分的期刊加罗马数字分卷标签
                f_item['page_label'] = self.to_roman_num(count) if journal_total_pages[j_name] > 1 else ""

                # 全天该期刊总文章数（用于显示 x/y 篇）
                if j_name in ['ArXiv Preprints (领域追踪)', 'Scholar Updates (学者动态)']:
                    f_item['total_nu'] = f_item['articles_nu']
                else:
                    f_item['total_nu'] = next(
                        (p['articles_nu'] for p in today_info['paper'] if p['journal'] == j_name),
                        f_item['articles_nu']
                    )

                # 跨页续篇复用同一序号（不再递增），确保同一期刊始终是同一个数字
                f_item['journal_global_idx'] = journal_idx_map[j_name]

                for article in f_item['data']:
                    article['global_idx'] = global_idx
                    global_idx += 1

            
            # 准备渲染上下文，始终保留全天指标
            page_info = self._build_page_info(
                today_info,
                page_papers,
                current_page=idx + 1,
                total_pages=total_pages,
                is_first_page=is_first_page,
                full_report=False,
            )
            
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
                metadata={
                    'date': today_info['today'],
                    'page': idx+1,
                    'total_pages': total_pages,
                    'count': sum(f['articles_nu'] for f in page_papers),
                    'disable_split': True,
                }
            ))
            
        # 生成一份包含全天所有数据的完整 HTML 用于本地查阅 (OVERWRITE latest.html with FULL data)
        full_info = self._build_page_info(
            today_info,
            today_info['paper'],
            current_page=1,
            total_pages=1,
            is_first_page=True,
            full_report=True,
        )
        full_html = self._generate_html(full_info)
        out_path = os.path.join(os.path.dirname(__file__), '../../output/paper/latest.html')
        os.makedirs(os.path.dirname(out_path), exist_ok=True)
        with open(out_path, 'w', encoding='utf-8') as f:
            f.write(full_html)
        print(f"[Paper] Unified full report saved to: {out_path} ({len(full_html)} bytes)")

        self._run_audit['includedArticles'] = today_info['articles_sum']
        self._run_audit['includedJournals'] = today_info['journals']
        self._write_run_audit()

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
        keyword_info = self._analyze_keywords(paper)
        return keyword_info['has_keyword'], keyword_info['all']
    
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
        self._run_audit['sourceMode'] = _source_mode
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
        """从 Semantic Scholar 获取学者动态（仅推送从未推过的新论文，基于 D1 去重）"""
        # 暂时禁用，避免产生额外页面和学科外论文
        return []

        if not authors:
            return []
        
        all_s2 = []
        now = datetime.now()
        # 用 1 年作为宽松兜底，避免拉不到数据；真正去重靠 D1
        cutoff = now - timedelta(days=365)

        for name, author_id in authors.items():
            self.logger.info(f"[Paper] Tracking Scholar {name} (ID: {author_id})")
            try:
                url = f"https://api.semanticscholar.org/graph/v1/author/{author_id}/papers"
                params = {'fields': 'title,url,year,publicationDate,authors,abstract', 'limit': 10}
                r = requests.get(url, params=params, timeout=15,
                                 proxies={"http": None, "https": None})
                data = r.json()
                
                if 'data' in data:
                    for p in data['data']:
                        pub_date_str = p.get('publicationDate') or f"{p.get('year', '2000')}-01-01"
                        
                        # 宽松日期兜底过滤（防止太古老的文章）
                        try:
                            pub_dt = datetime.strptime(pub_date_str[:10], '%Y-%m-%d')
                            if pub_dt < cutoff:
                                continue
                        except Exception:
                            pass

                        art = {
                            'title': p['title'],
                            'link': p['url'],
                            'author': ", ".join([a['name'] for a in p.get('authors', [])]),
                            'content': p.get('abstract') or "(无摘要)",
                            'journal': f"Scholar: {name}",
                            'date': pub_date_str
                        }

                        # D1 去重：只推送从未推过的论文
                        if not self._is_new_paper(art):
                            self.logger.debug(f"[Paper] S2 skip (already sent): {p['title'][:60]}")
                            continue

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

    def _get_data_from_d1(self) -> dict:
        """从 D1 数据库获取数据"""
        from core.d1_client import D1Client
        d1 = D1Client()
        if not d1.enabled:
            print("[Paper] D1 is disabled. Falling back to RSS.")
            return self._get_data_from_rss()
            
        self._ensure_article_batch_columns(d1)
        self._backfill_legacy_article_finalization(d1)
        self._run_audit['inflightRowsSkipped'] = self._count_inflight_rows(d1)

        limit = int(os.getenv('PAPER_ARTICLE_LIMIT', 0))
        sql = self._build_d1_article_sql(limit)
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
        
        print(f"[Paper] D1 returned {len(real_rows)} raw articles (based on first_seen_at).")
        self._run_audit['rawRows'] = len(real_rows)
        if not real_rows:
            return {"journals": 0, "today": datetime.now().strftime("%Y-%m-%d"), 
                    "articles_sum": 0, "journals_title": [], "paper": []}

        current_rows = self._dedupe_current_window_rows(real_rows)

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

        for item in current_rows:
            row = item['row']
            identity = item['identity']
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
                'id': row.get('id'),
                'published_at': row.get('published_at') or '',
                'created_at': row.get('created_at') or '',
                'dedupe_key': identity['dedupe_key'],
                'dedupe_kind': identity['dedupe_kind'],
                'doi': identity['doi'],
            }
            
            self._decorate_keyword_rendering(art)
            # 只有 GENERAL_JOURNALS 中的期刊才需要强制关键词命中
            # D1 模式已通过 SQL created_at 时间窗口过滤，无需再用 published_at 二次过滤
            j_name_lower = j_name.lower()
            in_general = any(j_name_lower == g.lower() for g in self.GENERAL_JOURNALS)
            if j_type == 'journal' and in_general and not art['is_include_keyword']:
                self._run_audit['skippedKeyword'] += 1
                self._append_audit_example('keywordExamples', {
                    'source': raw_j_name,
                    'title': art['title'],
                    'publishedAt': art['published_at'],
                    'createdAt': art['created_at'],
                })
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
            # 不截断：光学期刊不允许丢文章，综合期刊已由关键词过滤。每页容量由 MAX_PAGE_SIZE 控制
            articles = info['data']
            final_paper_data.append({
                "journal": j_name, "data": articles,
                "articles_nu": len(articles), "type": info['type']
            })
            total_articles_sum += len(articles)

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

        # 并行抓取，但保持原始 feeds_info 的顺序
        print(f"[Paper] Starting parallel fetch for {len(feeds_info)} feeds...")
        total_articles_sum = 0
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            # 按原始顺序提交，用列表保留顺序（不用 as_completed 以避免乱序）
            futures = [executor.submit(self._fetch_feed, f) for f in feeds_info]
            results = [f.result() for f in futures]  # 按提交顺序等待
        
        # 按原始顺序处理结果
        raw_results = []
        for res in results:
            if not res:
                continue
            journal_title = res['journal']
            raw_articles = res['articles']
            f_type = res.get('type', 'journal')
            raw_results.append((journal_title, raw_articles, f_type))
        
        # 过滤：研究人员在前，期刊保持原始顺序
        researcher_data = []
        journal_data = []
        
        for journal_title, raw_articles, f_type in raw_results:
            # 不截断：光学期刊不允许丢文章，综合期刊已由关键词过滤，每页容量由 MAX_PAGE_SIZE 控制
            
            filtered_list = []
            ino = 1
            for art in raw_articles:
                # 1. 时间过滤
                if not self._filter_date(art, journal_title):
                    continue
                
                # 2. 关键词检测
                self._decorate_keyword_rendering(art)
                
                # 3. 期刊筛选逻辑 (通用期刊必须包含关键词)
                if f_type == 'journal' and journal_title.lower() in self._general_journals_lower and not art['is_include_keyword']:
                    continue
                
                # 4. LLM 摘要 (如果有)
                if self.llm_provider and (art['is_include_keyword'] or self.test_mode):
                    try:
                        clean_text = re.sub(r'<[^>]+>', '', art['content']).strip()
                        txt_input = f"Title: {art['title']}\nAbstract: {clean_text[:2000]}"
                        art['summary'] = self.llm_provider.summarize(txt_input)
                    except:
                        pass
                
                art['id'] = ino
                filtered_list.append(art)
                ino += 1
            
            if filtered_list:
                entry = {
                    "journal": journal_title,
                    "data": filtered_list,
                    "articles_nu": len(filtered_list),
                    "type": f_type
                }
                if f_type == 'researcher':
                    researcher_data.append(entry)
                else:
                    journal_data.append(entry)
                total_articles_sum += len(filtered_list)
        
        # 研究人员在前，期刊按原始 INI 顺序
        final_paper_data = researcher_data + journal_data

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
            'update_time': datetime.now(timezone(timedelta(hours=8))).strftime("%Y-%m-%d %H:%M:%S"),
            'is_first_page': today_info.get('is_first_page', True),
            'current_page': today_info.get('current_page', 1),
            'total_pages': today_info.get('total_pages', 1),
            'full_report': today_info.get('full_report', False),
            'total_journals': today_info.get('total_journals') or today_info.get('journals', 0),
            'total_articles_sum': today_info.get('total_articles_sum') or today_info.get('articles_sum', 0),
            'paper': today_info.get('paper', []),
            'in_docker': self.in_docker
        }
        
        try:
            return template.render(**context)
        except Exception as e:
            print(f"[Paper] WARNING: Template render failed: {e}")
            import traceback; traceback.print_exc()
            return self._generate_html_legacy(today_info)

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
