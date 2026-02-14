"""Estate Source - Real Estate Data (Cloudflare D1)"""
import sys, os, time, re, requests
import logging
from bs4 import BeautifulSoup
from sources.base import BaseSource
from core import Message, ContentType
from core.d1_client import D1Client

class EstateSource(BaseSource):
    def __init__(self, topic='me', **kwargs):
        super().__init__(**kwargs)
        self.topic = topic
        self.logger = logging.getLogger('Push.Source.Estate')
        
        # Initialize D1 Client
        self.d1 = D1Client()
        
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

    def _scrape_chengdu(self):
        """
        Scrape Chengdu Real Estate Data
        Source: https://www.cdzjryb.com/SCXX/Default.aspx?action=ucEveryday2
        Ported from legacy/estate/chengdu_day.py
        """
        url = "https://www.cdzjryb.com/SCXX/Default.aspx?action=ucEveryday2"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        data_points = []
        today_str = time.strftime('%Y-%m-%d')
        
        try:
            self.logger.info("Fetching Chengdu data...")
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                self.logger.error(f"Chengdu fetch failed: {resp.status_code}")
                return []
                
            soup = BeautifulSoup(resp.content, 'html.parser')
            tables = soup.find_all('table', class_='blank')
            
            if not tables:
                self.logger.error("Chengdu: No data tables found")
                return []

            # Mapping based on legacy code
            # Table 0: New Homes (Commercial)
            # Table 1: Second Hand (Secondary)
            
            # Helper to extract number
            def get_num(text):
                matches = re.findall(r'-?\d+\.?\d*', text)
                return float(matches[0]) if matches else 0.0

            # 1. New Homes (全市/All) -> Table 0, Row 3 (Index 4 in legacy logic seems 1-based? Let's verify legacy code)
            # Legacy code says: 'com_all_house_area':(4,3) -> Row index 4, Col index 3
            # Beautiful Soup find_all('tr') is 0-indexed. 
            # Legacy logic: row = table[0].find_all("tr")[value[0]] -> value is (4, X).
            # So row index 4.
            
            t0 = tables[0]
            rows_t0 = t0.find_all("tr")
            if len(rows_t0) > 4:
                # New Home Area (sqm)
                nh_area = get_num(rows_t0[4].find_all("td")[3].get_text())
                data_points.append({'city': 'Chengdu', 'category': 'NewHome_Area', 'value': nh_area, 'unit': 'sqm'})
                # New Home Count (units)
                nh_count = get_num(rows_t0[4].find_all("td")[2].get_text())
                data_points.append({'city': 'Chengdu', 'category': 'NewHome_Count', 'value': nh_count, 'unit': 'units'})

            # 2. Second Hand (全市/All) -> Table 1, Row 4
            t1 = tables[1]
            rows_t1 = t1.find_all("tr")
            if len(rows_t1) > 4:
                # Second Hand Area (sqm)
                sh_area = get_num(rows_t1[4].find_all("td")[3].get_text())
                data_points.append({'city': 'Chengdu', 'category': 'SecondHand_Area', 'value': sh_area, 'unit': 'sqm'})
                # Second Hand Count (units)
                sh_count = get_num(rows_t1[4].find_all("td")[2].get_text())
                data_points.append({'city': 'Chengdu', 'category': 'SecondHand_Count', 'value': sh_count, 'unit': 'units'})
                
        except Exception as e:
            self.logger.error(f"Chengdu scrape error: {e}")
            
        return data_points

    def _push_to_d1(self, data_points):
        """Push data points to D1"""
        if not self.d1.enabled or not data_points:
            return

        today_str = time.strftime('%Y-%m-%d')
        
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
                today_str, 
                dp['city'], 
                dp['category'], 
                dp['value'], 
                dp['unit']
            ])
            if res['success']:
                success_count += 1
        
        self.logger.info(f"D1 Push: {success_count}/{len(data_points)} records saved.")

    def _scrape_xian(self):
        """
        Scrape Xi'an Real Estate Data
        Source: https://xa.anjuke.com/sale/ (Anjuke)
        Note: Fang.com and Beike have strict anti-bot/DNS issues in this env.
        """
        url = "https://xa.anjuke.com/sale/"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://xa.anjuke.com/'
        }
        
        data_points = []
        
        try:
            self.logger.info("Fetching Xi'an data (Anjuke)...")
            resp = requests.get(url, headers=headers, timeout=15)
            if resp.status_code != 200:
                self.logger.error(f"Xi'an fetch failed: {resp.status_code}")
                return []
            
            # Use Regex to find total count
            # Anjuke often puts count in JSON or HTML like "total": 1234
            # Debug showed recurrence of a specific number (e.g. 5369)
            # We try a few strict patterns first
            
            count = 0
            # Pattern 1: <span class="num">...</span>
            # Pattern 2: "total": 1234
            
            # Blind regex strategy based on debug check (matches 'total...digits')
            matches = re.findall(r'total.*?(\d+)', resp.text, re.IGNORECASE)
            if matches:
                 # Filter reasonable numbers (e.g. > 100)
                 # Debug showed '5369'
                 valid_nums = [float(m) for m in matches if float(m) > 100]
                 if valid_nums:
                     count = valid_nums[0] # Take the first reasonable number
            
            if count > 0:
                data_points.append({'city': 'Xian', 'category': 'SecondHand_Count_Anjuke', 'value': count, 'unit': 'units'})
            else:
                self.logger.warning("Xi'an: No valid count found in Anjuke page")

        except Exception as e:
            self.logger.error(f"Xi'an scrape error: {e}")
            
        return data_points

    def run(self) -> Message:
        # 1. Initialize DB
        self._init_db()
        
        # 2. Collect Data
        all_data = []
        
        # Chengdu
        cd_data = self._scrape_chengdu()
        all_data.extend(cd_data)
        
        # Xi'an
        xa_data = self._scrape_xian() 
        all_data.extend(xa_data)
        
        # 3. Store to D1
        if self.d1.enabled:
            self._push_to_d1(all_data)
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
