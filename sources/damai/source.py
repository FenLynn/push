
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
        
        # Load from Config (All cities)
        self.cities = config.get_damai_cities()
        
        # Filter if specific city requested via CLI
        if city_code:
            if city_code in self.cities:
                self.cities = {city_code: self.cities[city_code]}
            else:
                self.logger = logging.getLogger('Push.Source.Damai')
                self.logger.warning(f"Requested city '{city_code}' not found in config.")
                self.cities = {}

        self.logger = logging.getLogger('Push.Source.Damai')
        self.template_engine = TemplateEngine()

    def _process_city(self, city_code, venues):
        """Process a single city and return a list of Message objects (pages)"""
        city_name = self.city_name_map.get(city_code, city_code.capitalize())
        all_events = []
        
        # 1. Scrape Venues
        print(f"[Damai] Scraping {len(venues)} venues in {city_name} (ShowStart)...")
        for v in venues:
            evts = self._get_venue_events(v)
            all_events.extend(evts)
        
        # 2. Deduplicate
        unique_events = {}
        for e in all_events:
            if e['link'] not in unique_events:
                unique_events[e['link']] = e
        events_list = list(unique_events.values())
        
        # 3. Sort
        def parse_time(t_str):
            try:
                return time.strptime(t_str, "%Y/%m/%d %H:%M")
            except:
                return time.localtime()
        events_list.sort(key=lambda x: parse_time(x['raw_time']))
        
        # 4. Filter Past
        now_ts = time.time()
        future_events = []
        for e in events_list:
             try:
                 ts = time.mktime(parse_time(e['raw_time']))
                 if ts >= now_ts - 86400: # Include today
                     future_events.append(e)
             except:
                 future_events.append(e)
        
        if not future_events:
            return []

        # 5. Pagination
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
                tags=['damai', city_code]
            ))
            
            remaining = remaining[len(current_page_events):]
            page_num += 1
            if page_num > 10: break
            
        return pages

    def run(self):
        final_results = []
        
        # If no config, try default Fallback?
        if not self.cities:
             # If config is totally empty, maybe we should warn logic?
             # For now, return empty message for 'Chengdu' default
             return self._create_empty_msg('chengdu')

        for city, venues in self.cities.items():
            msgs = self._process_city(city, venues)
            if msgs:
                final_results.extend(msgs)
        
        # Logic: If NO events in ANY city -> Send one "No events" msg
        if not final_results:
            # Picks the first configured city to show "No events"
            first_city = list(self.cities.keys())[0] if self.cities else 'chengdu'
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
