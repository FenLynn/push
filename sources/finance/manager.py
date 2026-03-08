import pandas as pd
import json
import os
import logging
from core.db import db
from core.image_upload import upload_image_to_cdn

class DataManager:
    def __init__(self):
        self.tag_file = os.path.join(os.path.dirname(__file__), 'tag.json')
        self.logger = logging.getLogger('Push.Finance.Manager')
        self.d1_client = self._init_d1()
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

        # 2. Check Cache
        try:
            latest_date = str(df.iloc[-1]['date'])
            # Clean seconds if needed
            if '.' in latest_date: latest_date = latest_date.split('.')[0]
        except:
            latest_date = "unknown"

        if not force and name in self.tags:
            cached = self.tags[name]
            cached_date = cached.get('date')
            # Compare logic: check if strings match (both cleaned)
            if cached_date == latest_date and cached.get('url'):
                self.logger.debug(f"{name} skipped (Cached: {latest_date})")
                return False, cached.get('url')
        
        return True, latest_date

    def save_plot_info(self, name: str, date_str: str, pic_path: str):
        """上传图片并保存缓存 - R2 优先，SMMS 备用"""
        url = None

        # 1. 优先尝试 R2（自建存储，稳定）
        try:
            from core.image_upload import R2Uploader
            r2 = R2Uploader()
            if r2.s3:
                object_key = f"finance/{name}/{date_str}.png"
                url = r2.upload_file(pic_path, object_name=object_key)
                if url:
                    self.logger.info(f"✅ R2 上传成功 {name}: {url}")
        except Exception as e:
            self.logger.warning(f"R2 上传失败 ({name}): {e}")

        # 2. R2 失败时降级到 SMMS
        if not url:
            try:
                from core.image_upload import upload_image_with_cdn
                url = upload_image_with_cdn(pic_path)
                if url:
                    self.logger.info(f"✅ SMMS 上传成功 {name}: {url}")
            except Exception as e:
                self.logger.warning(f"SMMS 上传失败 ({name}): {e}")

        if not url:
            self.logger.error(f"❌ 图片上传全部失败: {name}")
            return None

        # 3. 更新本地缓存 & D1
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
