
import requests
import re
import time
import logging
from core import SourceInterface, Message, ContentType
from core.template import TemplateEngine
from core.config import config
from sources.base import BaseSource

class DamaiSource(BaseSource):
    """
    大麦/秀动演出源
    Since Damai.cn blocks TTRSS/Crawlers with WAF, we pivot to ShowStart (秀动).
    Strategy: Aggregate events from specific Top Venues in Chengdu.
    """
    
    def __init__(self, city_code='chengdu', topic='me'):
        super().__init__()
        self.topic = topic
        # City Logic
        self.city_code = city_code.lower()
        self.city_name_map = {'chengdu': '成都', 'xian': '西安'}
        self.city = self.city_name_map.get(self.city_code, '成都')
        
        # Load from Config
        self.venues = config.get_damai_venues(self.city_code)
        
        # Fallback if config is empty/missing
        if not self.venues:
             print(f"[Damai] Warning: No venues found in config.ini for {self.city_code}")
             # Hardcoded fallback for chengdu just in case? Or empty.
        
        self.logger = logging.getLogger(f'Push.Source.Damai.{self.city_code}')
        self.template_engine = TemplateEngine()

    def _get_venue_events(self, venue):
        """Fetch events for a single venue"""
        url = f"https://www.showstart.com/venue/{venue['id']}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        events = []
        try:
            # self.logger.info(f"Fetching {venue['name']}...")
            resp = requests.get(url, headers=headers, timeout=8)
            resp.encoding = 'utf-8' # Enforce UTF-8 to fix garbled text
            
            if resp.status_code != 200:
                self.logger.warning(f"Failed to fetch {venue['name']}: {resp.status_code}")
                return []

            # Regex for literal fields (Most common)
            # pattern = r'id:(\d+),title:"(.*?)",poster:"(.*?)".*?price:"(.*?)"'
            
            # Revised Regex to capture Price if literal, or ignore if variable
            # We look for `id:...,title:...,poster:...` and optionally `price:...,showTime:...`
            # Note: The order seems consistent in Nuxt dump.
            
            # Using findall with a pattern that allows price to be anything until comma
            regex = r'id:(\d+),title:"(.*?)",poster:"(.*?)".*?price:(.*?),showTime:"(.*?)"'
            
            raw_matches = re.findall(regex, resp.text)
            
            for m in raw_matches:
                eid, title, poster, price_raw, show_time = m
                
                # Check price
                # If price_raw is like "¥100", use it.
                # If price_raw is "f", use default.
                if '"' in price_raw:
                    price = price_raw.strip('"')
                else:
                    price = "点击查看"
                
                # Clean up unicode escapes
                # Robust Unicode Unescape using Regex to avoid corrupting existing UTF-8 chars
                def unescape_func(match):
                    return chr(int(match.group(1), 16))
                
                if '\\u' in title:
                    title = re.sub(r'\\u([0-9a-fA-F]{4})', unescape_func, title)
                
                poster = poster.replace(r'\u002F', '/') # Fix slashed URL
                show_time = show_time.replace(r'\u002F', '/') # Fix date formatting

                # Construct Event
                evt = {
                    'title': title,
                    'time': show_time,
                    'is_today': False,
                    'price': price,
                    'venue': venue['name'],
                    'img': poster if poster.startswith('http') else 'https:' + poster,
                    'link': f"https://www.showstart.com/event/{eid}",
                    'raw_time': show_time
                }
                
                events.append(evt)
                
        except Exception as e:
            self.logger.error(f"Error parsing {venue['name']}: {e}")
            
        return events

    def run(self) -> Message:
        all_events = []
        
        # 1. Scrape Venues
        print(f"[Damai] Scraping {len(self.venues)} venues in {self.city} (ShowStart)...")
        for v in self.venues:
            evts = self._get_venue_events(v)
            all_events.extend(evts)
            # print(f"  {v['name']}: {len(evts)}")
        
        # 2. Deduplicate (by Link/ID)
        unique_events = {}
        for e in all_events:
            if e['link'] not in unique_events:
                unique_events[e['link']] = e
        
        events_list = list(unique_events.values())
        
        # 3. Sort by Time
        def parse_time(t_str):
            try:
                return time.strptime(t_str, "%Y/%m/%d %H:%M")
            except:
                return time.localtime() # Fallback
                
        events_list.sort(key=lambda x: parse_time(x['raw_time']))
        
        # 4. Filter Past Events
        now_ts = time.time()
        future_events = []
        for e in events_list:
             try:
                 ts = time.mktime(parse_time(e['raw_time']))
                 if ts >= now_ts - 86400: # Include today logic
                     future_events.append(e)
             except:
                 future_events.append(e)
        
        # 5. Pagination & Render
        MAX_CHARS = 19800  # Maximize usage (User Request: 19800)
        pages = []
        remaining = future_events[:]
        page_num = 1
        
        if not remaining:
             html = self.template_engine.render('damai.html', {
                'title': f'{self.city}演出票务', 'city': self.city, 
                'date': time.strftime("%Y-%m-%d"), 'events': []
             })
             return Message(title=f'{self.city}演出(无)', content=html, type=ContentType.HTML)

        while remaining:
            current_page_events = []
            last_valid_html = ""
            temp_list = []
            
            for evt in remaining:
                temp_list.append(evt)
                # Render check
                html = self.template_engine.render('damai.html', {
                    'title': f'{self.city}演出票务',
                    'city': self.city,
                    'date': time.strftime("%Y-%m-%d"),
                    'events': temp_list
                })
                
                # Minify
                html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
                html = re.sub(r'>\s+<', '><', html)
                html = re.sub(r'\s+', ' ', html).strip()
                
                # Check Length (Characters)
                if len(html) > MAX_CHARS:
                    if len(temp_list) == 1:
                        current_page_events = temp_list
                         # If single item exceeds, we must calculate its html to ensure content is set
                        last_valid_html = html 
                    else:
                        current_page_events = temp_list[:-1]
                        # last_valid_html already holds the HTML for N-1 items
                    break
                else:
                    current_page_events = temp_list
                    last_valid_html = html
            
            # Commit Page
            title_suffix = f" P{page_num}" if (page_num > 1 or len(remaining) > len(current_page_events)) else ""
            
            # Use last_valid_html as content. 
            # If temp_list was 1 and it broke, last_valid_html was empty in old code? 
            # FIX: In old code, if break on first item, last_valid_html was "". 
            # I added `last_valid_html = html` in the break block above for single item case.
            
            if not last_valid_html and current_page_events:
                 # Should not happen with fix, but regenerate just in case
                 last_valid_html = self.template_engine.render('damai.html', {
                    'title': f'{self.city}演出票务',
                    'city': self.city,
                    'date': time.strftime("%Y-%m-%d"),
                    'events': current_page_events
                })
                 last_valid_html = re.sub(r'<!--.*?-->', '', last_valid_html, flags=re.DOTALL)
                 last_valid_html = re.sub(r'>\s+<', '><', last_valid_html)
                 last_valid_html = re.sub(r'\s+', ' ', last_valid_html).strip()

            pages.append(Message(
                title=f'{self.city}演出({time.strftime("%m-%d")}){title_suffix}',
                content=last_valid_html,
                type=ContentType.HTML,
                tags=['damai', 'showstart', self.city]
            ))
            
            remaining = remaining[len(current_page_events):]
            page_num += 1
            if page_num > 10: break
            
        print(f"[Damai] Total Unique: {len(events_list)} -> Future: {len(future_events)} -> Pages: {len(pages)}")
        
        return pages if len(pages) > 1 else pages[0]

if __name__ == '__main__':
    # Test
    s = DamaiSource()
    res = s.run()
    print("Test run complete.")
