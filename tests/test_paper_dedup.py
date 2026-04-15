#!/usr/bin/env python3
"""Paper 去重逻辑测试。"""

import os
import sys
from types import SimpleNamespace
from datetime import datetime, timedelta


ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT_DIR)

import scripts.fetch_to_d1 as fetch_to_d1_module
from channels.pushplus import PushPlusChannel
from core import ContentType, Message
from core.config import config
from core.engine import Engine
from core.image_upload import R2Uploader
from core.llm_factory import LLMFactory
from scripts.fetch_to_d1 import ARTICLE_RETENTION_DAYS, is_entry_within_retention
from sources.paper import PaperSource


def test_retention_window_filter():
    now = datetime(2026, 4, 12, 19, 0, 0)
    assert is_entry_within_retention(now - timedelta(days=ARTICLE_RETENTION_DAYS - 1), now)
    assert not is_entry_within_retention(now - timedelta(days=ARTICLE_RETENTION_DAYS + 1), now)


def test_dedupe_key_ignores_tracking_params():
    source = PaperSource(topic='me', test_mode=True)
    article_a = {
        'title': 'Navigating optical skyrmions-from historical origins to applications: tutorial',
        'link': 'https://example.org/paper?id=42&utm_source=rss&utm_campaign=test',
        'content': '',
        'published_at': '2025-12-23 05:00:00',
        'created_at': '2026-04-12 19:00:00',
    }
    article_b = {
        'title': 'Navigating optical skyrmions-from historical origins to applications: tutorial',
        'link': 'https://example.org/paper?id=42&utm_medium=mail',
        'content': '',
        'published_at': '2025-12-23 05:00:00',
        'created_at': '2026-04-12 20:00:00',
    }

    key_a = source._build_push_dedupe_identity(article_a, 'Advances in Optics and Photonics')
    key_b = source._build_push_dedupe_identity(article_b, 'Advances in Optics and Photonics')
    assert key_a['dedupe_key'] == key_b['dedupe_key']
    assert key_a['dedupe_kind'] == 'title'


def test_dedupe_key_separates_same_title_across_sources():
    source = PaperSource(topic='me', test_mode=True)
    article = {
        'title': 'Editorial',
        'link': '',
        'content': '',
        'published_at': '2026-04-06 05:00:00',
        'created_at': '2026-04-09 20:01:24',
    }

    key_a = source._build_push_dedupe_identity(article, 'Journal of Lightwave Technology')
    key_b = source._build_push_dedupe_identity(article, 'Optics Express')
    assert key_a['dedupe_key'] != key_b['dedupe_key']


def test_process_feed_skips_old_entries_before_insert():
    class FakeD1Client:
        def __init__(self):
            self.calls = []

        def query(self, sql, params):
            self.calls.append({'sql': sql, 'params': params})
            return {'success': True, 'data': [{'results': []}]}

    class Entry(SimpleNamespace):
        def get(self, key, default=''):
            return getattr(self, key, default)

    now = datetime.now()
    old_entry = Entry(
        link='https://example.org/old-paper',
        title='Old paper',
        published_parsed=(now - timedelta(days=ARTICLE_RETENTION_DAYS + 1)).timetuple(),
        summary='<p>Old abstract</p>',
        author='Old Author',
        doi='10.1000/old-paper'
    )
    recent_entry = Entry(
        link='https://example.org/recent-paper',
        title='Recent paper',
        published_parsed=(now - timedelta(hours=2)).timetuple(),
        summary='<p>Recent abstract</p>',
        author='Recent Author',
        doi='10.1000/recent-paper'
    )

    original_fetch_feed = fetch_to_d1_module.fetch_feed
    fetch_to_d1_module.fetch_feed = lambda url: SimpleNamespace(entries=[old_entry, recent_entry])
    try:
        fake_d1 = FakeD1Client()
        result = fetch_to_d1_module.process_feed_and_insert(
            {'title': 'Test Feed', 'url': 'https://example.org/feed.xml', 'type': 'journal'},
            fake_d1,
            batch_id='batch-1',
        )
    finally:
        fetch_to_d1_module.fetch_feed = original_fetch_feed

    assert result['inserted'] == 1
    assert result['skipped_old'] == 1
    assert result['fetch_failed'] is False
    assert len(fake_d1.calls) == 2
    article_call = fake_d1.calls[-1]
    assert article_call['sql'].count('?') == len(article_call['params'])
    assert article_call['params'][15] == 'batch-1'
    assert article_call['params'][16] is None
    assert article_call['params'][-1] is not None


def test_keyword_rendering_only_keeps_abstract_tail_tags():
    source = PaperSource(topic='me', test_mode=True)
    source.CHN_KEYWORDS = []
    source.ENG_KEYWORDS = ['fiber laser', 'optical']

    article = {
        'title': 'A compact fiber laser cavity for sensing',
        'content': '<p>Optical control is discussed in the abstract.</p>',
    }

    source._decorate_keyword_rendering(article)

    assert '<span class="kh">fiber laser</span>' in article['title_html']
    assert 'fiber laser' not in [item.lower() for item in article['display_keywords']]
    assert [item.lower() for item in article['display_keywords']] == ['optical']


def test_title_rendering_inserts_soft_hyphen_breaks():
    source = PaperSource(topic='me', test_mode=True)
    rendered = source._render_title_keyword_html('Microstructuredwaveguides for nonlinear optics', [])
    assert '&shy;' in rendered


def test_paper_llm_disabled_by_default():
    source = PaperSource(topic='me', test_mode=True)
    assert source.paper_llm_enabled is False
    assert source.llm_provider is None


def test_llm_config_strips_inline_env_comments():
    keys = ['LLM_PROVIDER', 'LLM_API_KEY', 'LLM_BASE_URL', 'LLM_MODEL', 'LLM_PROXY']
    old_values = {key: os.environ.get(key) for key in keys}
    try:
        os.environ['LLM_PROVIDER'] = 'zhipu       # zhipu | gemini | openai'
        os.environ['LLM_API_KEY'] = '             # missing key'
        os.environ['LLM_BASE_URL'] = '            # 可选:自定义API地址(反向代理)'
        os.environ['LLM_MODEL'] = 'glm-4-flash   # model hint'
        os.environ['LLM_PROXY'] = '               # proxy hint'

        llm_conf = config.get_llm_config()
        assert llm_conf['provider'] == 'zhipu'
        assert llm_conf['api_key'] == ''
        assert llm_conf['base_url'] == ''
        assert llm_conf['model'] == 'glm-4-flash'
        assert llm_conf['proxy'] == ''
    finally:
        for key, value in old_values.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_llm_factory_ignores_invalid_base_url_override():
    provider = LLMFactory.create_provider({
        'provider': 'zhipu',
        'api_key': 'demo-key',
        'base_url': '# invalid',
        'model': 'glm-4-flash',
    })
    assert provider is not None
    assert provider.base_url == 'https://open.bigmodel.cn/api/paas/v4'


def test_extract_entry_datetime_prefers_published_over_updated():
    entry = SimpleNamespace(
        published_parsed=datetime(2026, 4, 14, 8, 0, 0).timetuple(),
        updated_parsed=datetime(2026, 4, 14, 9, 0, 0).timetuple(),
    )
    dt, source = fetch_to_d1_module.extract_entry_datetime(entry)
    assert dt == datetime(2026, 4, 14, 8, 0, 0)
    assert source == 'published'


def test_evaluate_ingest_health_marks_stale_when_last_seen_too_old():
    health = fetch_to_d1_module.evaluate_ingest_health(
        {'latest_last_seen': '2026-04-12 19:01:31'},
        {'latest_last_seen': '2026-04-12 19:01:31'},
        total_new=0,
        fetch_failed_total=0,
        now=datetime(2026, 4, 14, 14, 30, 0),
    )
    assert health['status'] == 'stale'
    assert any('latest_last_seen_stale' in item for item in health['reasons'])


def test_evaluate_ingest_health_warns_on_zero_insert_without_change():
    health = fetch_to_d1_module.evaluate_ingest_health(
        {'latest_last_seen': '2026-04-14 10:00:00'},
        {'latest_last_seen': '2026-04-14 10:00:00'},
        total_new=0,
        fetch_failed_total=0,
        now=datetime(2026, 4, 14, 14, 30, 0),
    )
    assert health['status'] == 'warning'
    assert 'no_new_articles_and_no_d1_change' in health['reasons']


def test_split_page_by_render_length_rebalances_oversized_page():
    source = PaperSource(topic='me', test_mode=True)
    original_max_page_size = source.MAX_PAGE_SIZE
    original_generate_html = source._generate_html

    source.MAX_PAGE_SIZE = 120
    source._generate_html = lambda page_info: 'x' * (40 + 50 * sum(len(feed['data']) for feed in page_info['paper']))
    try:
        pages = source._split_page_by_render_length(
            {'today': '2026-04-15', 'journals': 1, 'articles_sum': 3},
            [{
                'journal': 'Test Journal',
                'data': [{'title': 'A'}, {'title': 'B'}, {'title': 'C'}],
                'articles_nu': 3,
            }],
        )
    finally:
        source.MAX_PAGE_SIZE = original_max_page_size
        source._generate_html = original_generate_html

    assert len(pages) == 3
    assert all(sum(len(feed['data']) for feed in page) == 1 for page in pages)


def test_flatten_paginated_segments_merges_same_journal_across_boundaries():
    source = PaperSource(topic='me', test_mode=True)
    flattened = source._flatten_paginated_segments([
        [{'journal': 'Journal A', 'data': [{'title': 'A1'}, {'title': 'A2'}], 'articles_nu': 2}],
        [
            {'journal': 'Journal A', 'data': [{'title': 'A3'}], 'articles_nu': 1},
            {'journal': 'Journal B', 'data': [{'title': 'B1'}], 'articles_nu': 1},
        ],
    ])

    assert [feed['journal'] for feed in flattened] == ['Journal A', 'Journal B']
    assert len(flattened[0]['data']) == 3
    assert len(flattened[1]['data']) == 1


def test_global_render_rebalance_can_merge_small_tail_pages():
    source = PaperSource(topic='me', test_mode=True)
    original_max_page_size = source.MAX_PAGE_SIZE
    original_generate_html = source._generate_html

    source.MAX_PAGE_SIZE = 150
    source._generate_html = lambda page_info: 'x' * (20 + 25 * sum(len(feed['data']) for feed in page_info['paper']))
    try:
        flattened = source._flatten_paginated_segments([
            [{'journal': 'Journal A', 'data': [{'title': 'A1'}, {'title': 'A2'}, {'title': 'A3'}], 'articles_nu': 3}],
            [{'journal': 'Journal A', 'data': [{'title': 'A4'}], 'articles_nu': 1}],
            [{'journal': 'Journal B', 'data': [{'title': 'B1'}, {'title': 'B2'}, {'title': 'B3'}], 'articles_nu': 3}],
            [{'journal': 'Journal B', 'data': [{'title': 'B4'}], 'articles_nu': 1}],
        ])
        pages = source._split_page_by_render_length(
            {'today': '2026-04-15', 'journals': 2, 'articles_sum': 8},
            flattened,
        )
    finally:
        source.MAX_PAGE_SIZE = original_max_page_size
        source._generate_html = original_generate_html

    assert [sum(len(feed['data']) for feed in page) for page in pages] == [5, 3]


def test_engine_respects_disable_split_metadata():
    class StaticSource:
        def run(self):
            return Message(
                title='paper-test',
                content='x' * 50,
                type=ContentType.HTML,
                metadata={'disable_split': True},
            )

    class RecordingChannel:
        def __init__(self):
            self.messages = []

        def send(self, message):
            self.messages.append(message)
            return True

    engine = Engine()
    engine.save_output = lambda *args, **kwargs: ''
    engine.splitter.max_length = 10
    engine.register_source('paper', StaticSource())
    recorder = RecordingChannel()
    engine.register_channel('recording', recorder)

    assert engine.run_source('paper', ['recording']) is True
    assert len(recorder.messages) == 1


def test_pushplus_send_respects_disable_split_metadata():
    channel = PushPlusChannel(token='demo-token', topic='me')
    sent_messages = []
    original_send_single = channel._send_single
    channel._send_single = lambda message: sent_messages.append(message) or True
    try:
        success = channel.send(Message(
            title='paper-test',
            content='x' * 19950,
            type=ContentType.HTML,
            metadata={'disable_split': True},
        ))
    finally:
        channel._send_single = original_send_single

    assert success is True
    assert len(sent_messages) == 1


def test_r2_uploader_accepts_standard_cloudflare_account_id_env():
    keys = {
        'CLOUDFLARE_R2_ACCOUNT_ID': os.environ.get('CLOUDFLARE_R2_ACCOUNT_ID'),
        'CLOUDFLARE_ACCOUNT_ID': os.environ.get('CLOUDFLARE_ACCOUNT_ID'),
        'CLOUDFLARE_AccountId': os.environ.get('CLOUDFLARE_AccountId'),
        'CLOUDFLARE_R2_ACCESS_KEY_ID': os.environ.get('CLOUDFLARE_R2_ACCESS_KEY_ID'),
        'CLOUDFLARE_R2_SECRET_ACCESS_KEY': os.environ.get('CLOUDFLARE_R2_SECRET_ACCESS_KEY'),
        'CLOUDFLARE_R2_BUCKET_NAME': os.environ.get('CLOUDFLARE_R2_BUCKET_NAME'),
    }
    try:
        os.environ.pop('CLOUDFLARE_R2_ACCOUNT_ID', None)
        os.environ.pop('CLOUDFLARE_AccountId', None)
        os.environ['CLOUDFLARE_ACCOUNT_ID'] = 'account-123'
        os.environ['CLOUDFLARE_R2_ACCESS_KEY_ID'] = 'access-key'
        os.environ['CLOUDFLARE_R2_SECRET_ACCESS_KEY'] = 'secret-key'
        os.environ['CLOUDFLARE_R2_BUCKET_NAME'] = 'bucket-name'

        assert R2Uploader.has_credentials() is True
        assert R2Uploader._resolve_account_id() == 'account-123'
    finally:
        for key, value in keys.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def test_crossref_exact_title_fallback(monkeypatch=None):
    item = {
        'title': 'Intelligent metrology of grating microstructures via fusion of diffraction spectra and a hybrid MaLSTM deep learning model',
        'journal': 'Optics & Laser Technology',
        'authors_text': '',
        'published_at': '2026-04-11 09:01:14',
    }

    exact_payload = {
        'message': {
            'items': [
                {
                    'title': [item['title']],
                    'container-title': ['Optics & Laser Technology'],
                    'DOI': '10.1016/j.optlastec.2026.115237',
                    'volume': '201',
                    'page': '115237',
                    'published-print': {'date-parts': [[2026, 9, 1]]},
                }
            ]
        }
    }

    original_fetch_crossref_json = fetch_to_d1_module.fetch_crossref_json
    calls = []

    def fake_fetch_crossref_json(url, params=None):
        calls.append(params or {})
        if params and params.get('query.bibliographic'):
            return {'message': {'items': []}}
        if params and params.get('query.title'):
            return exact_payload
        return None

    fetch_to_d1_module.fetch_crossref_json = fake_fetch_crossref_json
    try:
        result = fetch_to_d1_module.resolve_crossref_metadata(item)
    finally:
        fetch_to_d1_module.fetch_crossref_json = original_fetch_crossref_json

    assert result is not None
    assert result['doi'] == '10.1016/J.OPTLASTEC.2026.115237'
    assert any(call.get('query.title') for call in calls)


def test_paper_d1_query_uses_only_finalized_rows():
    source = PaperSource(topic='me', test_mode=True)
    sql = source._build_d1_article_sql(limit=20)
    assert "COALESCE(ingest_finalized_at, '') != ''" in sql
    assert "COALESCE(NULLIF(first_seen_at, ''), created_at)" in sql
    assert sql.endswith(' LIMIT 20')


def test_window_dedup_keeps_one_row_per_identity():
    source = PaperSource(topic='me', test_mode=True)
    rows = [
        {
            'title': 'Navigating optical skyrmions-from historical origins to applications: tutorial',
            'link': 'https://example.org/paper?id=42&utm_source=rss',
            'content': 'short',
            'published_at': '2026-04-12 09:00:00',
            'created_at': '2026-04-12 09:00:01',
            'first_seen_at': '2026-04-12 09:00:01',
            'last_seen_at': '2026-04-12 09:00:01',
            'source_name': 'Advances in Optics and Photonics',
            'doi': '',
            'authors': '',
        },
        {
            'title': 'Navigating optical skyrmions-from historical origins to applications: tutorial',
            'link': 'https://example.org/paper?id=42&utm_medium=mail',
            'content': 'much richer content',
            'published_at': '2026-04-12 09:00:00',
            'created_at': '2026-04-12 09:05:01',
            'first_seen_at': '2026-04-12 09:00:01',
            'last_seen_at': '2026-04-12 09:05:01',
            'source_name': 'Advances in Optics and Photonics',
            'doi': '10.1000/skyrmions',
            'authors': 'Alice',
        },
    ]

    deduped = source._dedupe_current_window_rows(rows)
    assert len(deduped) == 1
    assert deduped[0]['row']['doi'] == '10.1000/skyrmions'
    assert source._run_audit['skippedDuplicateRows'] == 1


def test_crossref_scoring_prefers_exact_candidate():
    item = {
        'title': 'Narrow-linewidth fiber laser with tunable output',
        'journal': 'Optics Express',
        'authors_text': 'Alice Zhang, Bob Li',
        'published_at': '2026-04-12 07:01:00',
    }
    exact = {
        'title': 'Narrow-linewidth fiber laser with tunable output',
        'journal': 'Optics Express',
        'authors': ['Alice Zhang'],
        'doi': '10.1000/exact',
        'published_at': '2026-04-12',
    }
    weak = {
        'title': 'Broadband photonic filter for imaging',
        'journal': 'Nature Communications',
        'authors': ['Charlie Wang'],
        'doi': '10.1000/weak',
        'published_at': '2024-03-01',
    }

    assert fetch_to_d1_module.score_crossref_search_candidate(item, exact) > fetch_to_d1_module.score_crossref_search_candidate(item, weak)


if __name__ == '__main__':
    test_retention_window_filter()
    test_dedupe_key_ignores_tracking_params()
    test_dedupe_key_separates_same_title_across_sources()
    test_process_feed_skips_old_entries_before_insert()
    test_keyword_rendering_only_keeps_abstract_tail_tags()
    test_crossref_scoring_prefers_exact_candidate()
    test_crossref_exact_title_fallback()
    test_paper_d1_query_uses_only_finalized_rows()
    print('paper dedupe tests passed')