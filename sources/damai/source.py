
import requests
import re
import time
import json
import os
import logging
from core import SourceInterface, Message, ContentType
from core.template import TemplateEngine
from core.config import config
from sources.base import BaseSource
from core.d1_client import D1Client

class DamaiSource(BaseSource):
    """
    大麦/秀动演出源
    Since Damai.cn blocks TTRSS/Crawlers with WAF, we pivot to ShowStart (秀动).
    Strategy: Aggregate events from specific Top Venues in Chengdu.
    """
    
    def __init__(self, city_code=None, topic='me', **kwargs):
        super().__init__(**kwargs)
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
        self.root_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        self.d1 = D1Client()
        if self.d1.enabled:
            # Ensure KV table exists
            self.d1.ensure_table('sys_kv', """
                CREATE TABLE sys_kv (
                    key TEXT PRIMARY KEY,
                    value TEXT,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)

    def _get_balanced(self, s, start_idx, open_char='(', close_char=')'):
        depth = 0
        for i in range(start_idx, len(s)):
            if s[i] == open_char: depth += 1
            elif s[i] == close_char:
                depth -= 1
                if depth == 0: return i
        return -1

    def _recursive_decode(self, text):
        """Iteratively decode unicode escapes and fix Mojibake (max 5 levels)"""
        if not text:
            return text
        
        current = text
        for _ in range(5):
            changed = False
            # 1. Unicode Escapes
            if '\\u' in current:
                try:
                    decoded = current.encode('utf-8').decode('unicode_escape')
                    if decoded != current:
                        current = decoded
                        changed = True
                except:
                    pass
            
            # 2. Mojibake correction (e.g. UTF-8 read as Latin-1)
            try:
                if any(ord(c) > 127 for c in current):
                    # Check if it looks like UTF-8 that was mis-decoded as Latin-1
                    # A quick check is to see if we can encode it as Latin-1
                    candidate = current.encode('latin1').decode('utf-8')
                    if candidate != current:
                        current = candidate
                        changed = True
            except:
                pass
                
            if not changed:
                break
        return current

    def _load_seen_ids(self):
        # 1. Try D1 first (Cloud persistence)
        if self.d1.enabled:
            try:
                res = self.d1.query("SELECT value FROM sys_kv WHERE key = 'damai_seen_ids'", [])
                if res['success'] and res['data'] and res['data'][0]['results']:
                    val_str = res['data'][0]['results'][0]['value']
                    return json.loads(val_str)
            except Exception as e:
                self.logger.warning(f"Failed to load seen_ids from D1: {e}")

        # 2. Fallback to local file
        path = os.path.join(self.root_dir, 'data', 'damai_seen_ids.json')
        if os.path.exists(path):
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except: pass
        return {}

    def _save_seen_ids(self, seen_dict):
        # 1. Save to D1 (Cloud persistence)
        if self.d1.enabled:
            try:
                val_str = json.dumps(seen_dict, ensure_ascii=False)
                sql = "INSERT OR REPLACE INTO sys_kv (key, value, updated_at) VALUES (?, ?, datetime('now'))"
                self.d1.query(sql, ['damai_seen_ids', val_str])
            except Exception as e:
                self.logger.warning(f"Failed to save seen_ids to D1: {e}")

        # 2. Save to local file (Backup / Local dev)
        path = os.path.join(self.root_dir, 'data', 'damai_seen_ids.json')
        os.makedirs(os.path.dirname(path), exist_ok=True)
        try:
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(seen_dict, f, ensure_ascii=False, indent=2)
        except Exception as e:
            self.logger.error(f"Failed to save seen IDs: {e}")

    def _top_level_split(self, s):
        res = []
        current = []
        depth = 0
        in_quote = False
        quote_char = None
        i = 0
        while i < len(s):
            char = s[i]
            if char in ('"', "'"):
                if not in_quote:
                    in_quote = True
                    quote_char = char
                elif quote_char == char:
                    # check for escaped quote
                    prev_backslashes = 0
                    j = i - 1
                    while j >= 0 and s[j] == '\\':
                        prev_backslashes += 1
                        j -= 1
                    if prev_backslashes % 2 == 0:
                        in_quote = False
            
            if not in_quote:
                if char in ('{', '['): depth += 1
                elif char in ('}', ']'): depth -= 1
                elif char == ',' and depth == 0:
                    res.append("".join(current).strip())
                    current = []
                    i += 1
                    continue
            current.append(char)
            i += 1
        res.append("".join(current).strip())
        return res

    def _fetch_city_events(self, city_name, city_code, page=1):
        """Fetch events for a single page of a city"""
        url = f"https://www.showstart.com/event/list?cityCode={city_code}&pageNo={page}"
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': 'https://www.showstart.com/event/list'
        }
        
        events = []
        try:
            self.logger.info(f"Fetching {city_name} Page {page}...")
            resp = requests.get(url, headers=headers, timeout=15)
            resp.encoding = 'utf-8'
            
            if resp.status_code != 200:
                return []

            # 1. Extract Nuxt Data hydration block
            start_marker = 'window.__NUXT__='
            start_idx = resp.text.find(start_marker)
            if start_idx == -1: return []
            
            end_idx = resp.text.find('</script>', start_idx)
            nuxt_js = resp.text[start_idx:end_idx].strip()
            if nuxt_js.endswith(';'): nuxt_js = nuxt_js[:-1].strip()
            
            payload = nuxt_js[len(start_marker):].strip()
            try:
                p_open = payload.find('(')
                p_close = self._get_balanced(payload, p_open)
                params_list = [p.strip() for p in payload[p_open+1 : p_close].split(',')]
                
                b_open = payload.find('{', p_close)
                b_close = self._get_balanced(payload, b_open, '{', '}')
                body_str = payload[b_open+1 : b_close]
                
                args_open = payload.find('(', b_close)
                args_close = self._get_balanced(payload, args_open)
                args_str = payload[args_open+1 : args_close]
                
                args_values = self._top_level_split(args_str)
                if params_list and params_list[-1] == '': params_list = params_list[:-1]
                
                mapping = dict(zip(params_list, args_values))
            except Exception as pe:
                self.logger.warning(f"Failed to parse hydration for {city_name} P{page}: {pe}")
                return []

            # 2. Extract from activityList
            al_start = body_str.find('activityList:[')
            search_scope = body_str[al_start:] if al_start != -1 else body_str
            id_matches = list(re.finditer(r'\{id:([a-zA-Z_0-9$]\w*),', search_scope))
            
            for i, match in enumerate(id_matches):
                start = match.start()
                end = id_matches[i+1].start() if i < len(id_matches)-1 else start + 1200
                chunk = search_scope[start:end]
                
                def find_field(key):
                    m = re.search(fr'{key}:([a-zA-Z_0-9$]\w*|"[^"]*")', chunk)
                    if m:
                        val_raw = m.group(1)
                        resolved = mapping.get(val_raw, val_raw)
                        return str(resolved).strip('"')
                    return None

                eid = find_field('id')
                title = find_field('title')
                price = find_field('price') or find_field('salesPrice') or find_field('basePrice')
                show_time = find_field('showTime')
                poster = find_field('poster')

                if not eid or not title or not eid.isdigit(): continue

                # Robust Unicode Decoding
                title = self._recursive_decode(title)
                
                poster = (poster or "").replace(r'\u002F', '/') 
                show_time = (show_time or "").replace(r'\u002F', '/')
                
                # Format price for template (strip symbols)
                clean_price = (price or "").replace('¥', '').replace('￥', '').strip()
                if clean_price and not clean_price.endswith('起'):
                    clean_price = f"{clean_price}起"
                elif not clean_price:
                    clean_price = "价格点此"

                events.append({
                    'title': title, 'time': show_time, 'is_today': False,
                    'price': clean_price, 'venue': city_name,
                    'img': poster if poster and poster.startswith('http') else 'https:' + (poster or ""),
                    'link': f"https://www.showstart.com/event/{eid}",
                    'raw_time': show_time
                })
                
        except Exception as e:
            self.logger.error(f"Error parsing city {city_name} P{page}: {e}")
            
        return events

    def _process_city(self, city_key, city_code):
        """Process multiple pages for a city"""
        city_name = self.city_name_map.get(city_key, city_key.capitalize())
        
        # 1. Fetch multiple pages (e.g. 1-4) to ensure we get past the sticky past events
        all_events = []
        for p in range(1, 4):
            page_events = self._fetch_city_events(city_name, city_code, page=p)
            if not page_events: break
            all_events.extend(page_events)
            time.sleep(1) # Be gentle
        
        self.logger.info(f"{city_name}: Fetched {len(all_events)} total events across pages.")

        # Dedup by ID
        seen_ids = set()
        unique_events = []
        for e in all_events:
            eid = e['link'].split('/')[-1]
            if eid not in seen_ids:
                unique_events.append(e)
                seen_ids.add(eid)
        
        # 2. Sort
        def parse_time(t_str):
            try:
                return time.strptime(t_str, "%Y/%m/%d %H:%M")
            except:
                return time.localtime()
        unique_events.sort(key=lambda x: parse_time(x['raw_time']))
        
        # 3. Filter Past & Incremental
        now_ts = time.time()
        today_str = time.strftime("%Y/%m/%d")
        incremental_events = []
        
        # Load local seen IDs
        history = self._load_seen_ids()
        city_history = history.get(city_code, {})
        
        # Migration & Cleanup: Handle old list-based format and remove expired items
        if isinstance(city_history, list):
            # Migrate from list to dict (temporary empty date)
            city_history = {eid: "" for eid in city_history}
        
        # Cleanup: Remove items older than today
        cleaned_history = {}
        for eid, show_date in city_history.items():
            if not show_date or show_date >= today_str:
                cleaned_history[eid] = show_date
        
        city_seen_dict = cleaned_history
        
        for e in unique_events:
             # Link format: https://www.showstart.com/event/289336
             eid = e['link'].split('/')[-1]
             # raw_time format: 2026/03/14 20:00 -> extract 2026/03/14
             show_date = e['raw_time'].split(' ')[0] if ' ' in e['raw_time'] else e['raw_time']
             
             # Skip if already seen (Absolute incremental)
             if not self.force and eid in city_seen_dict:
                 continue
                 
             try:
                 ts = time.mktime(parse_time(e['raw_time']))
                 if ts >= now_ts - 86400: # Include today
                     incremental_events.append(e)
                     # Track this new event with its date
                     city_seen_dict[eid] = show_date
             except:
                 incremental_events.append(e)
                 city_seen_dict[eid] = show_date
        
        self.logger.info(f"{city_name}: {len(incremental_events)} NEW events since last push.")
        
        # Update history (Save the cleaned and updated dict)
        history[city_code] = city_seen_dict
        self._save_seen_ids(history)

        if not incremental_events:
            return []

        # 4. Pagination
        MAX_CHARS = 19800
        pages = []
        remaining = incremental_events[:]
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
             return [] # No cities configured, return empty list

        for city_key, city_code in self.cities_config.items():
            msgs = self._process_city(city_key, city_code)
            if msgs:
                final_results.extend(msgs)
            else:
                # If city has no events, explicitly add an "Empty" message for this city
                # This ensures every configured city sends a push (e.g. "Chengdu: No events", "Xian: Events")
                final_results.append(self._create_empty_msg(city_key))
        
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
