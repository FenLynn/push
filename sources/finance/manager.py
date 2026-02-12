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
        self.tags = self._load_tags()

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
        # Use ASCII names to avoid encoding issues
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
        except:
            latest_date = "unknown"

        if not force and name in self.tags:
            cached = self.tags[name]
            if str(cached.get('date')) == latest_date and cached.get('url'):
                self.logger.debug(f"{name} skipped (Cached: {latest_date})")
                return False, cached.get('url')
        
        return True, latest_date

    def save_plot_info(self, name: str, date_str: str, pic_path: str):
        """上传图片并保存缓存 - 使用统一上传系统"""
        from core.image_upload import upload_image_with_cdn
        
        try:
            # Upload to SMMS with CDN (automatic rate limiting + retry)
            url = upload_image_with_cdn(pic_path)
            
            if url:
                self.tags[name] = {'date': str(date_str), 'url': url}
                self._save_tags()
                self.logger.info(f"✅ Saved {name}: {url}")
                return url
            else:
                self.logger.error(f"❌ Failed to upload {name}")
                return None
                
        except Exception as e:
            self.logger.error(f"Upload exception for {name}: {e}")
            return None
