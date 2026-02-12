
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
    
    def __init__(self, city_code=None, topic='me'):
        super().__init__()
        self.topic = topic
        self.city_code_filter = city_code
        self.city_name_map = {'chengdu': '成都', 'xian': '西安', 'beijing': '北京', 'shanghai': '上海'}
        
        # Load from Config (Cities Map: name -> code)
        # e.g. {'chengdu': '28', 'xian': '29'}
        self.cities_config = config.get_damai_cities()
        
        # Filter if specific city requested via CLI
        if city_code:
            if city_code in self.cities_config:
                self.cities_config = {city_code: self.cities_config[city_code]}
            else:
                self.logger = logging.getLogger('Push.Source.Damai')
                self.logger.warning(f"Requested city '{city_code}' not found in config.")
                # Try to use it anyway if it looks like a code? No, stick to config.
                self.cities_config = {}

        self.logger = logging.getLogger('Push.Source.Damai')
        self.template_engine = TemplateEngine()

    def _fetch_city_events(self, city_name, city_code):
        """Fetch events for a whole city using City Code"""
        url = f"https://www.showstart.com/event/list?cityCode={city_code}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        
        events = []
        try:
            print(f"[Damai] Fetching {city_name} (Code: {city_code})...")
            resp = requests.get(url, headers=headers, timeout=10)
            resp.encoding = 'utf-8'
            
            if resp.status_code != 200:
                self.logger.warning(f"Failed to fetch {city_name}: {resp.status_code}")
                return []

            # Regex for City List Page (Nuxt Dump)
            # Confirmed regex: id:(\d+),title:"(.*?)",poster:"(.*?)".*?price:(.*?),showTime:"(.*?)"
            regex = r'id:(\d+),title:"(.*?)",poster:"(.*?)".*?price:(.*?),showTime:"(.*?)"'
            
            raw_matches = re.findall(regex, resp.text)
            
            for m in raw_matches:
                eid, title, poster, price_raw, show_time = m
                
                # Clean up unicode
                def unescape_func(match):
                    return chr(int(match.group(1), 16))
                
                if '\\u' in title:
                    title = re.sub(r'\\u([0-9a-fA-F]{4})', unescape_func, title)
                
                # Clean Price
                price = price_raw.strip('"')
                if not price or price == 'ad': 
                    # fallback if regex captured 'ad' or junk
                    price = "点击查看" 
                
                poster = poster.replace(r'\u002F', '/') 
                show_time = show_time.replace(r'\u002F', '/')

                # Construct Event
                evt = {
                    'title': title,
                    'time': show_time,
                    'is_today': False,
                    'price': price,
                    'venue': city_name, # City list doesn't easily give venue name in this regex, use City for now
                    'img': poster if poster.startswith('http') else 'https:' + poster,
                    'link': f"https://www.showstart.com/event/{eid}",
                    'raw_time': show_time
                }
                
                events.append(evt)
                
        except Exception as e:
            self.logger.error(f"Error parsing city {city_name}: {e}")
            
        return events

    def _process_city(self, city_key, city_code):
        """Process a single city and return a list of Message objects"""
        city_name = self.city_name_map.get(city_key, city_key.capitalize())
        
        # 1. Fetch
        all_events = self._fetch_city_events(city_name, city_code)
        
        # 2. Sort
        def parse_time(t_str):
            try:
                return time.strptime(t_str, "%Y/%m/%d %H:%M")
            except:
                return time.localtime()
        all_events.sort(key=lambda x: parse_time(x['raw_time']))
        
        # 3. Filter Past
        now_ts = time.time()
        future_events = []
        for e in all_events:
             try:
                 ts = time.mktime(parse_time(e['raw_time']))
                 if ts >= now_ts - 86400: # Include today
                     future_events.append(e)
             except:
                 future_events.append(e)
        
        if not future_events:
            return []

        # 4. Pagination
        MAX_CHARS = 19800
        pages = []
        remaining = future_events[:]
        page_num = 1
        
        while remaining:
            current_page_events = []
            last_valid_html = ""
            temp_list = []
            
            for evt in remaining:
                temp_list.append(evt)
                html = self.template_engine.render('damai.html', {
                    'title': f'{city_name}演出票务', 'city': city_name,
                    'date': time.strftime("%Y-%m-%d"), 'events': temp_list
                })
                # Minify
                html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
                html = re.sub(r'>\s+<', '><', html)
                html = re.sub(r'\s+', ' ', html).strip()
                
                if len(html) > MAX_CHARS:
                    if len(temp_list) == 1:
                        current_page_events = temp_list
                        last_valid_html = html 
                    else:
                        current_page_events = temp_list[:-1]
                    break
                else:
                    current_page_events = temp_list
                    last_valid_html = html
            
            if not last_valid_html and current_page_events:
                 last_valid_html = self.template_engine.render('damai.html', {
                    'title': f'{city_name}演出票务', 'city': city_name,
                    'date': time.strftime("%Y-%m-%d"), 'events': current_page_events
                })
            
            title_suffix = f" P{page_num}" if (page_num > 1 or len(remaining) > len(current_page_events)) else ""
            
            pages.append(Message(
                title=f'{city_name}演出({time.strftime("%m-%d")}){title_suffix}',
                content=last_valid_html,
                type=ContentType.HTML,
                tags=['damai', city_key]
            ))
            
            remaining = remaining[len(current_page_events):]
            page_num += 1
            if page_num > 10: break
            
        return pages

    def run(self):
        final_results = []
        
        if not self.cities_config:
             return self._create_empty_msg('chengdu')

        for city_key, city_code in self.cities_config.items():
            msgs = self._process_city(city_key, city_code)
            if msgs:
                final_results.extend(msgs)
        
        # Logic: If NO events in ANY city -> Send one "No events" msg
        if not final_results:
            first_city = list(self.cities_config.keys())[0] if self.cities_config else 'chengdu'
            return self._create_empty_msg(first_city)
            
        return final_results

    def _create_empty_msg(self, city_code):
        city_name = self.city_name_map.get(city_code, city_code.capitalize())
        html = self.template_engine.render('damai.html', {
            'title': f'{city_name}演出票务', 'city': city_name, 
            'date': time.strftime("%Y-%m-%d"), 'events': []
        })
        return Message(title=f'{city_name}演出(无)', content=html, type=ContentType.HTML)

if __name__ == '__main__':
    # Test
    s = DamaiSource()
    res = s.run()
    print("Test run complete.")
