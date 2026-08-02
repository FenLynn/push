"""Estate Source - Real Estate Data (Cloudflare D1)"""
import base64
import datetime
import hashlib
import hmac
import secrets
import sys, os, time, re, requests
import logging
import pandas as pd
import akshare as ak
from bs4 import BeautifulSoup
from urllib.parse import urljoin
from sources.base import BaseSource
from core import Message, ContentType
from core.d1_client import D1Client
from core.dashboard_snapshot import export_dashboard_snapshot, load_dashboard_snapshot
from core.data_archive import DataArchive

class EstateSource(BaseSource):
    def __init__(self, topic='me', **kwargs):
        super().__init__(**kwargs)
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.Estate')
        
        # Initialize D1 Client
        self.d1 = D1Client()
        self.archive = DataArchive(self.d1)
        
        # Define Schema
        self.table_name = "estate_daily"
        self.schema_sql = """
        CREATE TABLE IF NOT EXISTS estate_daily (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            city TEXT NOT NULL,
            category TEXT NOT NULL,
            value REAL,
            unit TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(date, city, category, unit)
        );
        """

    def _init_db(self):
        """Ensure D1 table exists"""
        if self.d1.enabled:
            self.d1.ensure_table(self.table_name, self.schema_sql)

    @staticmethod
    def _parse_chengdu_timestamp(response):
        """Accept both response formats currently served by the public gateway."""
        try:
            payload = response.json()
        except (TypeError, ValueError):
            payload = {}
        timestamp = str(((payload.get('data') or {}).get('timestamp')) or '') if isinstance(payload, dict) else ''
        if timestamp:
            return timestamp

        text = str(getattr(response, 'text', '') or '')
        match = re.search(r'<timestamp>\s*(\d+)\s*</timestamp>', text, flags=re.I)
        if match:
            return match.group(1)
        raise ValueError('gateway timestamp missing')

    @classmethod
    def _request_chengdu_gateway(cls, base_url, resource, headers):
        time_response = requests.get(
            f'{base_url}/fplc/Ticket/getTime',
            headers=headers,
            timeout=30,
        )
        time_response.raise_for_status()
        timestamp = cls._parse_chengdu_timestamp(time_response)

        nonce = secrets.token_hex(4)
        message = f'{resource}:{timestamp}:{nonce}'.encode('utf-8')
        signature = base64.b64encode(
            hmac.new(b'fuadoifhasucvvapdanf', message, hashlib.md5).digest()
        ).decode('ascii')
        response = requests.post(
            f'{base_url}/fplc/Ticket/getDataWithLogin',
            json={
                'resource': resource,
                'data': {'data': {'queryDate': time.strftime('%Y-%m-%d')}},
            },
            headers={
                **headers,
                'X-Sign': signature,
                'X-Timestamp': timestamp,
                'X-Nonce': nonce,
            },
            timeout=35,
        )
        response.raise_for_status()
        payload = response.json()
        gateway_data = payload.get('data') if isinstance(payload, dict) else {}
        rows = gateway_data.get('data') if isinstance(gateway_data, dict) else []
        return [item for item in (rows or []) if isinstance(item, dict)]

    def _scrape_chengdu(self):
        """
        Read Chengdu's public daily transaction gateway.

        The legacy table now redirects to a SPA. The SPA uses a timestamped
        HMAC wrapper for its public daily endpoint, so the request is recreated
        here without browser state or account credentials.
        """
        base_url = "https://blmp.cdzjryb.com"
        resource = "/fcytx/qsmzq-all-api/qsmzq-zfytx-api/zjryb_mrcj"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
            'Accept': 'application/json, text/plain, */*',
            'Referer': f'{base_url}/fplc_daas_portal/#/todayDeal',
            'Origin': base_url,
            'Content-Type': 'application/json;charset=UTF-8',
        }

        self._last_chengdu_error = ''
        rows = []
        last_error = None
        for attempt in range(2):
            try:
                rows = self._request_chengdu_gateway(base_url, resource, headers)
                if rows:
                    break
                last_error = ValueError('public gateway returned no daily rows')
            except Exception as exc:
                last_error = exc
            if attempt == 0:
                time.sleep(0.6)

        if not rows:
            self._last_chengdu_error = str(last_error or 'public gateway returned no daily rows')
            self.logger.error(f"Chengdu gateway error: {last_error}")
            return []

        try:
            city_row = next(
                (item for item in rows if str(item.get('region_type') or '').strip() == '全市'),
                None,
            )
            if city_row is None:
                self.logger.warning("Chengdu gateway lacks an explicit citywide row; using the largest aggregate")
                city_row = max(
                    rows,
                    key=lambda item: float(item.get('clf_countnum') or 0) + float(item.get('spf_countnum') or 0),
                )
            source_date = str(city_row.get('dated') or time.strftime('%Y-%m-%d'))
            return [
                {'city': 'Chengdu', 'category': 'NewHome_Area', 'label': '新房成交面积', 'value': float(city_row.get('spf_area') or 0), 'unit': 'sqm', 'source': 'Chengdu-Housing-Bureau', 'quality': 'official', 'sourceDate': source_date},
                {'city': 'Chengdu', 'category': 'NewHome_Count', 'label': '新房成交套数', 'value': float(city_row.get('spf_countnum') or 0), 'unit': 'units', 'source': 'Chengdu-Housing-Bureau', 'quality': 'official', 'sourceDate': source_date},
                {'city': 'Chengdu', 'category': 'SecondHand_Area', 'label': '二手房成交面积', 'value': float(city_row.get('clf_area') or 0), 'unit': 'sqm', 'source': 'Chengdu-Housing-Bureau', 'quality': 'official', 'sourceDate': source_date},
                {'city': 'Chengdu', 'category': 'SecondHand_Count', 'label': '二手房成交套数', 'value': float(city_row.get('clf_countnum') or 0), 'unit': 'units', 'source': 'Chengdu-Housing-Bureau', 'quality': 'official', 'sourceDate': source_date},
            ]
        except Exception as exc:
            self._last_chengdu_error = str(exc)
            self.logger.error(f"Chengdu gateway parse error: {exc}")
            return []

    @staticmethod
    def _parse_xian_monthly_transaction_text(title, text, source_url=''):
        """Parse one official Xi'an monthly second-hand transaction notice."""
        title_text = re.sub(r'\s+', '', str(title or ''))
        month_match = re.search(r'(\d{4})年(\d{1,2})月份?二手房网签情况', title_text)
        if not month_match:
            return None

        normalized = re.sub(r'\s+', '', str(text or ''))
        total_match = re.search(
            r'(?:全市)?存量房(?:（二手房）)?网签备案(?:情况，)?面积(?:为)?([\d.]+)万平方米',
            normalized,
        )
        count_first = re.search(
            r'住宅网签备案(?:约)?(\d+)套[、，,；;]?(?:面积)?([\d.]+)万平方米',
            normalized,
        )
        area_first = re.search(
            r'住宅网签备案面积([\d.]+)万平方米[（(](\d+)套[）)]',
            normalized,
        )
        if count_first:
            residential_count = int(count_first.group(1))
            residential_area = float(count_first.group(2))
        elif area_first:
            residential_count = int(area_first.group(2))
            residential_area = float(area_first.group(1))
        else:
            residential_count = None
            residential_area = None

        return {
            'date': f'{int(month_match.group(1)):04d}-{int(month_match.group(2)):02d}-01',
            'second_hand_total_area': round(float(total_match.group(1)) * 10000, 2) if total_match else None,
            'second_hand_residential_count': residential_count,
            'second_hand_residential_area': round(residential_area * 10000, 2) if residential_area is not None else None,
            'source_url': str(source_url or ''),
        }

    @classmethod
    def _parse_xian_transaction_search_html(cls, html, page_url):
        soup = BeautifulSoup(str(html or ''), 'lxml')
        records = []
        for info in soup.select('.search_info'):
            links = [
                link for link in info.select('a[href]')
                if '/tjxx/' in str(link.get('href') or '') or '/fcscjy/' in str(link.get('href') or '')
            ]
            if not links:
                continue
            link = next((item for item in links if '/tjxx/' in str(item.get('href') or '')), links[0])
            title = link.get_text(' ', strip=True)
            source_url = urljoin(page_url, link.get('href', ''))
            record = cls._parse_xian_monthly_transaction_text(
                title,
                info.get_text(' ', strip=True),
                source_url,
            )
            if record:
                record['title'] = re.sub(r'\s+', ' ', title).strip()
                records.append(record)
        return records

    @staticmethod
    def _xian_transaction_complete(record):
        return all(record.get(key) is not None for key in (
            'second_hand_total_area',
            'second_hand_residential_count',
            'second_hand_residential_area',
        ))

    def _request_xian_public_page(self, url, params=None):
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://zjj.xa.gov.cn/',
        }
        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(url, params=params, headers=headers, timeout=(8, 30))
                response.raise_for_status()
                return response.content.decode('utf-8', errors='replace')
            except Exception as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"Xi'an official page failed: {last_error}")

    def _scrape_xian_monthly_transactions(self, max_pages=5):
        """Collect the official monthly second-hand signing history from public notices."""
        self._last_xian_transactions_error = ''
        search_url = 'https://zjj.xa.gov.cn/search.html'
        base_params = {
            'tab': 'all',
            'sortType': 'time',
            'scope': 'title,resourceSummary,resourceContent,mc_0_listtitle',
            'keywords': '网签情况',
        }
        by_month = {}
        try:
            for page in range(1, max(1, int(max_pages)) + 1):
                params = dict(base_params)
                if page > 1:
                    params.update({'page': page, 'keyAdd': 'false'})
                html = self._request_xian_public_page(search_url, params=params)
                records = self._parse_xian_transaction_search_html(html, search_url)
                for record in records:
                    existing = by_month.get(record['date'])
                    current_score = sum(value is not None for key, value in record.items() if key.startswith('second_hand_'))
                    existing_score = sum(value is not None for key, value in (existing or {}).items() if key.startswith('second_hand_'))
                    canonical = '/tjxx/' in record.get('source_url', '')
                    existing_canonical = '/tjxx/' in (existing or {}).get('source_url', '')
                    if existing is None or current_score > existing_score or (
                        canonical and not existing_canonical and current_score >= existing_score
                    ):
                        by_month[record['date']] = record

            for month, record in list(by_month.items()):
                if self._xian_transaction_complete(record):
                    continue
                detail_html = self._request_xian_public_page(record['source_url'])
                soup = BeautifulSoup(detail_html, 'lxml')
                for node in soup(['script', 'style']):
                    node.decompose()
                parsed = self._parse_xian_monthly_transaction_text(
                    record.get('title'),
                    soup.get_text(' ', strip=True),
                    record.get('source_url'),
                )
                if parsed:
                    by_month[month] = {**record, **parsed}
        except Exception as exc:
            self._last_xian_transactions_error = str(exc)
            self.logger.error("Xi'an monthly transaction fetch error: %s", exc)
            return []

        complete = [record for record in by_month.values() if self._xian_transaction_complete(record)]
        incomplete_count = len(by_month) - len(complete)
        if incomplete_count:
            self.logger.warning("Xi'an monthly transactions skipped %s incomplete notices", incomplete_count)
        if not complete:
            self._last_xian_transactions_error = 'official search returned no complete monthly records'
        return sorted(complete, key=lambda item: item['date'])

    @staticmethod
    def _latest_xian_transaction_points(records):
        if not records:
            return []
        latest = max(records, key=lambda item: item['date'])
        specs = (
            ('SecondHand_Residential_Count', '二手住宅网签套数', 'second_hand_residential_count', 'units'),
            ('SecondHand_Total_Area', '二手房网签总面积', 'second_hand_total_area', 'sqm'),
            ('SecondHand_Residential_Area', '二手住宅网签面积', 'second_hand_residential_area', 'sqm'),
        )
        return [{
            'city': 'Xian',
            'category': category,
            'label': label,
            'value': float(latest[field]),
            'unit': unit,
            'source': 'Xian-Housing-Bureau-Monthly-SecondHand',
            'quality': 'official',
            'sourceDate': latest['date'],
        } for category, label, field, unit in specs]

    def _archive_xian_monthly_transactions(self, records):
        if not records or not self.archive.enabled:
            return 0
        frame = pd.DataFrame(records)
        return self.archive.store_dataframe(
            domain='estate',
            group_name='transactions',
            frame=frame,
            metrics={
                'second_hand_residential_count': {'label': '二手住宅网签套数', 'unit': 'units'},
                'second_hand_total_area': {'label': '二手房网签总面积', 'unit': 'sqm'},
                'second_hand_residential_area': {'label': '二手住宅网签面积', 'unit': 'sqm'},
            },
            label='西安二手房月度网签',
            source='Xian-Housing-Bureau-Monthly-SecondHand',
            frequency='monthly',
            location='Xian',
            quality='official',
        )

    def _push_to_d1(self, data_points):
        """Push data points to D1"""
        if not self.d1.enabled or not data_points:
            return

        success_count = 0
        for dp in data_points:
            # Upsert logic (Insert or Replace) -> D1 supports standard SQL
            # We defined UNIQUE(date, city, category, unit)
            sql = """
            INSERT INTO estate_daily (date, city, category, value, unit)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(date, city, category, unit) 
            DO UPDATE SET value=excluded.value, timestamp=CURRENT_TIMESTAMP;
            """
            res = self.d1.query(sql, [
                str(dp.get('sourceDate') or time.strftime('%Y-%m-%d'))[:10],
                dp['city'], 
                dp['category'], 
                dp['value'], 
                dp['unit']
            ])
            if res['success']:
                success_count += 1
        
        self.logger.info(f"D1 Push: {success_count}/{len(data_points)} records saved.")

    def _fetch_price_index_history(self):
        """Fetch the long-running monthly 70-city price index for Chengdu/Xi'an."""
        try:
            frame = ak.macro_china_new_house_price(city_first='成都', city_second='西安')
            frame = frame.rename(columns={
                '日期': 'date',
                '城市': 'city_zh',
                '新建商品住宅价格指数-同比': 'new_home_yoy',
                '新建商品住宅价格指数-环比': 'new_home_mom',
                '二手住宅价格指数-同比': 'second_hand_yoy',
                '二手住宅价格指数-环比': 'second_hand_mom',
            })
            required = {'date', 'city_zh', 'new_home_yoy', 'new_home_mom', 'second_hand_yoy', 'second_hand_mom'}
            if not required.issubset(frame.columns):
                raise ValueError(f"unexpected price-index columns: {list(frame.columns)}")
            frame['date'] = pd.to_datetime(frame['date'], errors='coerce')
            return frame.dropna(subset=['date', 'city_zh']).sort_values('date')
        except Exception as exc:
            self.logger.error(f"City price-index fetch failed: {exc}")
            return pd.DataFrame()

    def _archive_price_index(self, frame):
        if frame is None or frame.empty or not self.archive.enabled:
            return []
        latest_items = []
        city_map = {'成都': 'Chengdu', '西安': 'Xian'}
        metric_specs = {
            'new_home_yoy': {'label': '新房价格同比指数', 'unit': 'index'},
            'new_home_mom': {'label': '新房价格环比指数', 'unit': 'index'},
            'second_hand_yoy': {'label': '二手房价格同比指数', 'unit': 'index'},
            'second_hand_mom': {'label': '二手房价格环比指数', 'unit': 'index'},
        }
        for city_zh, city in city_map.items():
            city_frame = frame[frame['city_zh'] == city_zh].copy()
            if city_frame.empty:
                continue
            self.archive.store_dataframe(
                domain='estate',
                group_name='city_price_index',
                frame=city_frame,
                metrics=metric_specs,
                label=f'{city_zh}住宅价格指数',
                source='AkShare/NBS-70-city',
                frequency='monthly',
                location=city,
                quality='official',
            )
            latest = city_frame.iloc[-1]
            source_date = latest['date'].strftime('%Y-%m-%d')
            for metric, spec in metric_specs.items():
                value = pd.to_numeric(latest.get(metric), errors='coerce')
                if pd.isna(value):
                    continue
                latest_items.append({
                    'city': city,
                    'category': metric,
                    'value': float(value),
                    'unit': spec['unit'],
                    'source': 'NBS-70-city',
                    'sourceDate': source_date,
                    'stale': False,
                })
        return latest_items

    @staticmethod
    def _count_presale_buildings(value):
        text = str(value or '').strip()
        if not text:
            return 0
        matches = re.findall(r'[^,，、;；\s]+?(?:幢|栋|号楼)', text)
        if matches:
            return len(set(matches))
        return len([item for item in re.split(r'[,，、;；\s]+', text) if item])

    @classmethod
    def _parse_xian_presale_html(cls, html, page_url):
        soup = BeautifulSoup(str(html or ''), 'lxml')
        events = []
        for row in soup.select('tr.listtr.ysztr'):
            cells = row.find_all('td', recursive=False)
            if len(cells) < 6:
                continue
            permit_no = cells[0].get_text(' ', strip=True)
            project = cells[1].get_text(' ', strip=True)
            address = cells[2].get_text(' ', strip=True)
            developer = cells[3].get_text(' ', strip=True)
            buildings = cells[4].get_text(' ', strip=True)
            issued_on = cells[5].get_text(' ', strip=True)
            if not permit_no or not project or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', issued_on):
                continue
            link = cells[1].find('a') or cells[0].find('a')
            source_url = urljoin(page_url, link.get('href', '')) if link else page_url
            events.append({
                'source': 'Xian-Housing-Bureau-Presale',
                'externalId': permit_no,
                'city': 'Xian',
                'eventType': 'presale_permit',
                'occurredOn': issued_on,
                'title': project,
                'sourceUrl': source_url,
                'quality': 'official',
                'detail': {
                    'permitNo': permit_no,
                    'project': project,
                    'address': address,
                    'developer': developer,
                    'buildings': buildings,
                    'buildingCount': cls._count_presale_buildings(buildings),
                },
            })
        return events

    def _request_xian_presale_page(self, page):
        base_url = 'https://zjj.xa.gov.cn/ygsf/index.aspx'
        url = base_url if page <= 1 else f'{base_url}?page={page}'
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/124 Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9',
            'Referer': 'https://zjj.xa.gov.cn/',
        }
        last_error = None
        for attempt in range(3):
            try:
                response = requests.get(url, headers=headers, timeout=(8, 30))
                response.raise_for_status()
                html = response.content.decode('utf-8', errors='replace')
                events = self._parse_xian_presale_html(html, url)
                if events:
                    return events
                last_error = ValueError('official page returned no recognizable permit rows')
            except Exception as exc:
                last_error = exc
            if attempt < 2:
                time.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f'Xi\'an official presale page {page} failed: {last_error}')

    def _scrape_xian_presales(self, lookback_days=45, max_pages=12):
        """Collect recent official presale permits; sparse dates are not filled with zeroes."""
        cutoff = datetime.date.today() - datetime.timedelta(days=max(1, int(lookback_days)))
        events = []
        seen = set()
        for page in range(1, max(1, int(max_pages)) + 1):
            try:
                page_events = self._request_xian_presale_page(page)
            except Exception as exc:
                if page == 1:
                    self.logger.error("Xi'an presale fetch error: %s", exc)
                    return []
                self.logger.warning("Xi'an presale pagination stopped on page %s: %s", page, exc)
                break
            oldest = None
            for event in page_events:
                event_date = datetime.date.fromisoformat(event['occurredOn'])
                oldest = min(oldest, event_date) if oldest else event_date
                if event_date < cutoff or event['externalId'] in seen:
                    continue
                seen.add(event['externalId'])
                events.append(event)
            if oldest and oldest < cutoff:
                break
        return sorted(events, key=lambda item: (item['occurredOn'], item['externalId']), reverse=True)

    @staticmethod
    def _aggregate_xian_presales(events):
        by_date = {}
        for event in events:
            issued_on = str(event.get('occurredOn') or '')
            if not issued_on:
                continue
            bucket = by_date.setdefault(issued_on, {'permits': set(), 'projects': set(), 'buildings': 0})
            bucket['permits'].add(str(event.get('externalId') or ''))
            bucket['projects'].add(str(event.get('title') or ''))
            bucket['buildings'] += int((event.get('detail') or {}).get('buildingCount') or 0)

        specs = (
            ('PresalePermit_Count', '商品房预售许可', 'permits', lambda value: len(value['permits'])),
            ('PresaleProject_Count', '预售项目', 'projects', lambda value: len(value['projects'])),
            ('PresaleBuilding_Count', '可售楼幢', 'buildings', lambda value: value['buildings']),
        )
        points = []
        for issued_on, bucket in sorted(by_date.items()):
            for category, label, unit, getter in specs:
                points.append({
                    'city': 'Xian',
                    'category': category,
                    'label': label,
                    'value': float(getter(bucket)),
                    'unit': unit,
                    'source': 'Xian-Housing-Bureau-Presale',
                    'quality': 'official',
                    'rollup': 'sum',
                    'sourceDate': issued_on,
                })
        return points

    def _merge_recent_snapshot(self, current_items):
        """Retain a city's last good values when one upstream fails temporarily."""
        today = time.strftime('%Y-%m-%d')
        merged = [dict(item, stale=False, sourceDate=str(item.get('sourceDate') or today)) for item in current_items]
        current_keys = {(item.get('city'), item.get('category')) for item in current_items}
        previous = load_dashboard_snapshot('estate') or {}
        payload = previous.get('payload') if isinstance(previous.get('payload'), dict) else {}
        previous_items = payload.get('items') if isinstance(payload.get('items'), list) else []
        generated_at = str(previous.get('generatedAt') or '')
        age_days = self._snapshot_age_days(generated_at)

        if age_days <= 7:
            for item in previous_items:
                city = item.get('city') if isinstance(item, dict) else None
                key = (city, item.get('category')) if isinstance(item, dict) else (None, None)
                if key[1] == 'SecondHand_Count_Anjuke':
                    continue
                if city and key not in current_keys:
                    cached_item = dict(item)
                    cached_item['stale'] = True
                    cached_item['sourceDate'] = str(item.get('sourceDate') or payload.get('date') or '')
                    merged.append(cached_item)
        return merged

    def _merge_recent_permits(self, current_events):
        if current_events:
            return [dict(item, stale=False) for item in current_events[:12]]
        previous = load_dashboard_snapshot('estate') or {}
        payload = previous.get('payload') if isinstance(previous.get('payload'), dict) else {}
        generated_at = str(previous.get('generatedAt') or '')
        cached = payload.get('recentPermits') if isinstance(payload.get('recentPermits'), list) else []
        if self._snapshot_age_days(generated_at) <= 7:
            return [dict(item, stale=True) for item in cached[:12] if isinstance(item, dict)]
        return []

    @staticmethod
    def _snapshot_age_days(generated_at):
        try:
            previous_time = datetime.datetime.fromisoformat(str(generated_at).replace('Z', '+00:00'))
            now = datetime.datetime.now(datetime.timezone.utc)
            return max(0, (now - previous_time.astimezone(datetime.timezone.utc)).total_seconds() / 86400)
        except (TypeError, ValueError):
            return float('inf')

    def run(self) -> Message:
        # 1. Initialize DB
        self._init_db()
        
        # 2. Collect Data
        current_data = []
        price_index_items = self._archive_price_index(self._fetch_price_index_history())
        
        # Chengdu
        cd_data = self._scrape_chengdu()
        current_data.extend(cd_data)

        # Xi'an publishes a monthly official second-hand signing report. This
        # is a transaction series and must not be mixed with daily presale supply.
        xian_transaction_records = self._scrape_xian_monthly_transactions()
        current_data.extend(self._latest_xian_transaction_points(xian_transaction_records))
        
        # Xi'an official presale supply. A day with no permit remains missing,
        # rather than being converted to a synthetic zero.
        xian_events = self._scrape_xian_presales()
        xian_supply_points = self._aggregate_xian_presales(xian_events)
        if xian_supply_points:
            latest_xian_date = max(item['sourceDate'] for item in xian_supply_points)
            current_data.extend([
                item for item in xian_supply_points if item['sourceDate'] == latest_xian_date
            ])

        all_data = self._merge_recent_snapshot(current_data + price_index_items)
        recent_permits = self._merge_recent_permits(xian_events)

        if all_data:
            export_dashboard_snapshot('estate', {
                'date': time.strftime('%Y-%m-%d'),
                'items': all_data,
                'cities': sorted(list(set(item['city'] for item in all_data))),
                'recentPermits': recent_permits,
            })
        
        # 3. Store to D1
        if self.d1.enabled:
            self._push_to_d1(cd_data + xian_supply_points)
            self.archive.store_points('estate', 'transactions', cd_data, 'Chengdu-Housing-Bureau')
            self._archive_xian_monthly_transactions(xian_transaction_records)
            self.archive.store_points('estate', 'presale_supply', xian_supply_points, 'Xian-Housing-Bureau-Presale')
            self.archive.store_estate_events(xian_events)
            self.archive.record_run(
                'estate',
                'chengdu_daily_transactions',
                'success' if cd_data else 'error',
                len(cd_data),
                str(getattr(self, '_last_chengdu_error', '') or ''),
            )
            self.archive.record_run(
                'estate',
                'xian_monthly_transactions',
                'success' if xian_transaction_records else 'error',
                len(xian_transaction_records),
                str(getattr(self, '_last_xian_transactions_error', '') or ''),
            )
            self.archive.run_retention()
        else:
            self.logger.warning("D1 config missing. Data NOT saved.")

        # 4. Generate Report
        text = f'🏠 房产观察日报 ({time.strftime("%Y-%m-%d")})\n'
        text += '--------------------------------\n'
        
        if not all_data:
            text += "⚠️ 今日暂无数据抓取成功\n"
        
        # Group by City
        cities = sorted(list(set(d['city'] for d in all_data)))
        for city in cities:
            text += f'【{city}】\n'
            city_data = [d for d in all_data if d['city'] == city]
            for item in city_data:
                # Format
                lbl = item['category'].replace('_', ' ')
                val = f"{int(item['value'])}" if item['unit'] == 'units' else f"{item['value']:.2f}"
                text += f"- {lbl}: {val} {item['unit']}\n"
            text += '\n'
            
        if self.d1.enabled:
            text += f"\n✅ 已归档至 Cloudflare D1"
        else:
            text += f"\n❌ D1 尚未配置，数据未保存"
            
        return Message(
            title=f'房产观察({time.strftime("%m-%d")})',
            content=text, 
            type=ContentType.TEXT, 
            tags=['estate', self.topic]
        )
