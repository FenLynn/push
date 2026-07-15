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
    def _request_chengdu_gateway(base_url, resource, headers):
        time_response = requests.get(
            f'{base_url}/fplc/Ticket/getTime',
            headers=headers,
            timeout=30,
        )
        time_response.raise_for_status()
        time_payload = time_response.json()
        timestamp = str(((time_payload.get('data') or {}).get('timestamp')) or '')
        if not timestamp:
            raise ValueError('gateway timestamp missing')

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
            'Referer': f'{base_url}/fplc_daas_portal/',
            'Content-Type': 'application/json',
        }

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
            self.logger.error(f"Chengdu gateway error: {last_error}")
            return []

        try:
            city_row = max(
                rows,
                key=lambda item: float(item.get('clf_countnum') or 0) + float(item.get('spf_countnum') or 0),
            )
            source_date = str(city_row.get('dated') or time.strftime('%Y-%m-%d'))
            return [
                {'city': 'Chengdu', 'category': 'NewHome_Area', 'value': float(city_row.get('spf_area') or 0), 'unit': 'sqm', 'sourceDate': source_date},
                {'city': 'Chengdu', 'category': 'NewHome_Count', 'value': float(city_row.get('spf_countnum') or 0), 'unit': 'units', 'sourceDate': source_date},
                {'city': 'Chengdu', 'category': 'SecondHand_Area', 'value': float(city_row.get('clf_area') or 0), 'unit': 'sqm', 'sourceDate': source_date},
                {'city': 'Chengdu', 'category': 'SecondHand_Count', 'value': float(city_row.get('clf_countnum') or 0), 'unit': 'units', 'sourceDate': source_date},
            ]
        except Exception as exc:
            self.logger.error(f"Chengdu gateway parse error: {exc}")
            return []

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

    def _scrape_xian(self):
        """
        Read Xi'an's public residential second-hand listing total.

        The former Anjuke desktop page now frequently returns a verification
        shell. Fang's mobile page exposes the current total as a hidden field
        and is used here without browser state.
        """
        url = "https://m.fang.com/esf/xian/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Linux; Android 13; Pixel 7) AppleWebKit/537.36 Chrome/120 Mobile Safari/537.36',
            'Accept-Language': 'zh-CN,zh;q=0.9',
        }

        try:
            self.logger.info("Fetching Xi'an data (Fang mobile)...")
            response = requests.get(url, headers=headers, timeout=(8, 25))
            response.raise_for_status()
            response.encoding = 'utf-8'
            match = re.search(r'data-id="total"\s+value="(\d+)"', response.text, re.IGNORECASE)
            count = int(match.group(1)) if match else 0
            if count <= 0:
                self.logger.warning("Xi'an: listing total missing from Fang mobile page")
                return []
            return [{
                'city': 'Xian',
                # Keep the legacy category so existing D1 history remains continuous.
                'category': 'SecondHand_Count_Anjuke',
                'value': count,
                'unit': 'units',
                'source': 'fang-mobile',
                'sourceDate': time.strftime('%Y-%m-%d'),
            }]
        except Exception as exc:
            self.logger.error(f"Xi'an Fang fetch error: {exc}")
            return []

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
                if city and key not in current_keys:
                    cached_item = dict(item)
                    cached_item['stale'] = True
                    cached_item['sourceDate'] = str(item.get('sourceDate') or payload.get('date') or '')
                    merged.append(cached_item)
        return merged

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
        
        # Xi'an
        xa_data = self._scrape_xian() 
        current_data.extend(xa_data)

        all_data = self._merge_recent_snapshot(current_data + price_index_items)

        if all_data:
            export_dashboard_snapshot('estate', {
                'date': time.strftime('%Y-%m-%d'),
                'items': all_data,
                'cities': sorted(list(set(item['city'] for item in all_data))),
            })
        
        # 3. Store to D1
        if self.d1.enabled:
            self._push_to_d1(current_data)
            transaction_points = [
                point for point in current_data
                if point.get('category') != 'SecondHand_Count_Anjuke'
            ]
            self.archive.store_points('estate', 'transactions', transaction_points, 'city-public-gateway')
            self.archive.run_retention()
        else:
            self.logger.warning("D1 config missing. Data NOT saved.")

        # 4. Generate Report
        text = f'🏠 房产成交日报 ({time.strftime("%Y-%m-%d")})\n'
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
            title=f'房产日报({time.strftime("%m-%d")})', 
            content=text, 
            type=ContentType.TEXT, 
            tags=['estate', self.topic]
        )
