import pandas as pd
import json
import os
import logging
from core.db import db
from core.data_archive import DataArchive
from .archive_catalog import ARCHIVE_CATALOG

class DataManager:
    def __init__(self):
        self.tag_file = os.path.join(os.path.dirname(__file__), 'tag.json')
        self.logger = logging.getLogger('Push.Finance.Manager')
        self.d1_client = self._init_d1()
        self.archive = DataArchive(self.d1_client) if self.d1_client else None
        self.df_cache = {}  # {indicator_name: df} —— 供 MacroDigest 等读取，避免重复 fetch
        # Load local first, then try to sync from D1
        self.tags = self._load_tags()
        self._sync_from_d1()

    def _init_d1(self):
        from core.d1_client import D1Client
        client = D1Client()
        if client.enabled:
            return client
        return None

    def _load_tags(self):
        if os.path.exists(self.tag_file):
            try:
                with open(self.tag_file, 'r') as f:
                    return json.load(f)
            except: 
                return {}
        return {}

    def _save_tags(self):
        with open(self.tag_file, 'w') as f:
            json.dump(self.tags, f, indent=4)

    def _sync_from_d1(self):
        """Fetch all tags from D1 and update local cache"""
        if not self.d1_client: return

        try:
            res = self.d1_client.query("SELECT * FROM finance_tags")
            if res.get('success'):
                rows = res.get('data', [])
                # Handle possible nested results structure from D1 REST API
                if rows and isinstance(rows, list) and len(rows) > 0:
                     if 'results' in rows[0]:
                         rows = rows[0]['results']
                
                if rows:
                    count = 0
                    for row in rows:
                        name = row.get('name')
                        if name:
                            self.tags[name] = {
                                'url': row.get('url'),
                                'date': row.get('date')
                            }
                            count += 1
                    self.logger.info(f"Synced {count} tags from D1.")
                    self._save_tags() # Update local cache file
        except Exception as e:
            self.logger.warning(f"D1 Sync failed: {e}")

    def check_update_needed(self, name: str, df: pd.DataFrame, force=False):
        """
        检查是否需要更新并保存数据到数据库
        Returns: (needs_update: bool, metadata: dict/str)
                 if needs_update: metadata is latest_date
                 else: metadata is cached_url
        """
        if df is None or df.empty:
            self.logger.warning(f"No data for {name}")
            return False, None

        # The chart cache is also the archive freshness marker.  Check it
        # before touching either SQLite or D1: scheduled finance jobs often
        # fetch the same latest date repeatedly, and re-archiving the full
        # history only creates redundant reads/writes.
        try:
            latest_date = str(df.iloc[-1]['date'])
            if '.' in latest_date:
                latest_date = latest_date.split('.')[0]
        except Exception:
            latest_date = "unknown"

        cache_hit = False
        cached_url = ''
        if name in self.tags:
            cached = self.tags[name]
            cached_date = cached.get('date')
            cached_url = str(cached.get('url') or '')
            expected_path = f"/finance/{name}/latest.png"
            cache_hit = cached_date == latest_date and expected_path in cached_url
            if cache_hit and not force:
                self.logger.debug(f"{name} skipped (Cached: {latest_date})")
                return False, cached_url

        archive_spec = ARCHIVE_CATALOG.get(name)
        if self.archive and archive_spec and not cache_hit:
            try:
                self.archive.store_dataframe(
                    domain='finance',
                    group_name=name,
                    frame=df,
                    metrics=archive_spec['metrics'],
                    label=archive_spec['label'],
                    source=archive_spec['source'],
                    frequency=archive_spec['frequency'],
                    quality=archive_spec.get('quality', 'official'),
                    replace_observations=archive_spec.get('replace_observations', False),
                )
            except Exception as exc:
                self.logger.warning(f"D1 archive failed for {name}: {exc}")

        # 1. Save to DB (Full Replace for Macro Data to ensure consistency)
        name_map = {
            '股债利差': 'erp',
            '两融杠杆率': 'leverage',
            '巴菲特指标': 'buffett',
            '流动性画像': 'liquidity',
            '克强指数': 'keqiang',
            '进出口贸易': 'trade'
        }
        ascii_name = name_map.get(name, name)
        table_name = f"finance_{ascii_name}"
        try:
            # 标准化日期 columns
            if 'date' not in df.columns and '日期' in df.columns:
                df['date'] = df['日期']
            
            # Save
            db.save_monitor_data(df, table_name, if_exists='replace')
        except Exception as e:
            self.logger.error(f"DB Save error: {e}")

        return True, latest_date

    def save_plot_info(self, name: str, date_str: str, pic_path: str):
        """Upload a chart to a stable R2 key and cache its public URL."""
        url = None

        try:
            from core.image_upload import R2Uploader
            r2 = R2Uploader()
            if r2.s3:
                object_key = f"finance/{name}/latest.png"
                url = r2.upload_file(pic_path, object_name=object_key)
                if url:
                    self.logger.info(f"R2 upload succeeded for {name}: {url}")
                    removed = r2.prune_prefix(f"finance/{name}/", keep_keys={object_key})
                    if removed:
                        self.logger.info(f"R2 rolling cleanup removed {removed} old object(s) for {name}")
        except Exception as e:
            self.logger.warning(f"R2 upload failed ({name}): {e}")

        if not url:
            self.logger.error(f"No public R2 URL available for chart: {name}")
            return None

        self.tags[name] = {'date': str(date_str), 'url': url}
        self._save_tags()

        if self.d1_client:
            try:
                clean_date = str(date_str)
                if '.' in clean_date: clean_date = clean_date.split('.')[0]
                sql = "INSERT OR REPLACE INTO finance_tags (name, url, date) VALUES (?, ?, ?)"
                self.d1_client.query(sql, [name, url, clean_date])
            except Exception as de:
                self.logger.warning(f"D1 更新失败 ({name}): {de}")

        return url
