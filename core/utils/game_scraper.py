
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
import re


SCORE_ENDPOINT = "https://bifen4pc2.qiumibao.com/json/{date}/v2/{match_id}.htm"


def _nullable_score(value):
    if value in (None, ''):
        return None
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return None


def normalize_score_payload(payload, match=None):
    """Normalize a zhibo8 score payload without guessing an unavailable state."""
    if not isinstance(payload, dict):
        return {}
    match = match or {}
    state = str(payload.get('state') or '').strip()
    period_text = str(payload.get('period_cn') or payload.get('period_state') or '').strip()
    if re.search(r'取消|延期|推迟', period_text):
        status = 'cancelled'
    elif state == '2':
        status = 'running'
    elif state == '3':
        status = 'finished'
    else:
        return {}

    left = payload.get('left') if isinstance(payload.get('left'), dict) else {}
    right = payload.get('right') if isinstance(payload.get('right'), dict) else {}
    score_a = _nullable_score(left.get('score'))
    score_b = _nullable_score(right.get('score'))
    current_game_match = re.search(r'第\s*(\d+)\s*局', period_text)
    current_game = int(current_game_match.group(1)) if current_game_match else None
    winner = ''
    if status == 'finished' and score_a is not None and score_b is not None and score_a != score_b:
        winner = str(match.get('team_a') if score_a > score_b else match.get('team_b') or '').strip()

    return {
        'status': status,
        'status_known': True,
        'live': status == 'running',
        'score_a': score_a,
        'score_b': score_b,
        'period_text': period_text,
        'current_game': current_game,
        'winner': winner,
    }

class GameSchedule:
    """直播8 (zhibo8.cc) 赛程抓取器"""
    
    URL = "https://www.zhibo8.cc/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.zhibo8.cc/"
    }

    def __init__(self, target_keywords=None):
        self.target_keywords = target_keywords or []

    def _fetch_score_status(self, match):
        match_id = str(match.get('id') or '').strip()
        date_str = str(match.get('date') or '').strip()
        if not match_id or not date_str:
            return match_id, {}
        try:
            response = requests.get(
                SCORE_ENDPOINT.format(date=date_str, match_id=match_id),
                headers=self.HEADERS,
                timeout=6,
            )
            if response.status_code != 200:
                return match_id, {}
            return match_id, normalize_score_payload(response.json(), match)
        except (requests.RequestException, ValueError):
            return match_id, {}

    def _enrich_started_matches(self, results):
        now = datetime.now()
        candidates = []
        for match in results:
            raw_time = str(match.get('raw_time') or '').strip()
            try:
                starts_at = datetime.strptime(raw_time, '%Y-%m-%d %H:%M')
            except ValueError:
                continue
            if starts_at.date() == now.date() and starts_at <= now:
                candidates.append(match)
        if not candidates:
            return

        by_id = {str(match.get('id') or ''): match for match in candidates}
        with ThreadPoolExecutor(max_workers=min(8, len(candidates))) as executor:
            futures = [executor.submit(self._fetch_score_status, match) for match in candidates]
            for future in as_completed(futures):
                match_id, status_data = future.result()
                if match_id in by_id and status_data:
                    by_id[match_id].update(status_data)

    def get_all_game_info(self) -> pd.DataFrame:
        """抓取并解析赛程"""
        try:
            response = requests.get(self.URL, headers=self.HEADERS, timeout=15)
            response.encoding = 'utf-8'
            if response.status_code != 200:
                print(f"[GameScraper] HTTP Error: {response.status_code}")
                return pd.DataFrame()
            
            soup = BeautifulSoup(response.text, 'lxml')
            # 使用更稳定的 li[data-time] 选择器
            items = soup.select('li[data-time]')
            
            results = []
            
            for li in items:
                raw_time = li.get('data-time', '') # 2026-02-12 17:00
                if not raw_time or len(raw_time) < 16:
                    continue
                
                date_str = raw_time[:10]
                time_str = raw_time[11:16]
                
                # 提取内容
                # 直播8的结构中，通常第一个 a 标签或 span 是联赛/类型
                # 我们寻找包含关键词的行
                match_text = li.get_text()
                
                should_include = False
                if not self.target_keywords:
                    should_include = True
                else:
                    for kw in self.target_keywords:
                        if kw.upper() in match_text.upper():
                            should_include = True
                            break
                
                if should_include:
                    # 1. 尝试识别游戏类型 (用于 UI 药丸标签)
                    game_type = "电竞"
                    search_text = match_text + " " + li.get('label', '')
                    type_keywords = {
                        '王者': '王者', 'KPL': '王者',
                        'LOL': 'LOL', 'LPL': 'LOL', 'LCK': 'LOL', '英雄联盟': 'LOL',
                        'DOTA2': 'Dota2', 'DOTA': 'Dota2', '刀塔': 'Dota2',
                        '乒乓': '乒乓', '足球': '足球', '篮球': '篮球', '网球': '网球',
                        '世界杯': '足球', '五大联赛': '足球'
                    }
                    for kw, val in type_keywords.items():
                        if kw.upper() in search_text.upper():
                            game_type = val
                            break
                    
                    # 2. 从 DOM 原生结构精准提取联赛名与队伍名
                    span_league = li.find('span', class_='_league')
                    span_teams = li.find('span', class_='_teams')
                    team_a_logo = ''
                    team_b_logo = ''
                    
                    if span_league and span_teams:
                        league = span_league.get_text(separator=" ", strip=True)
                        teams_str = span_teams.get_text(separator=" ", strip=True) # 使用空格分隔以免文字粘连
                        team_images = [str(image.get('src') or '').strip() for image in span_teams.find_all('img')]
                        team_a_logo = team_images[0] if len(team_images) > 0 else ''
                        team_b_logo = team_images[1] if len(team_images) > 1 else ''
                        
                        # 3. 安全分割主客队队伍
                        if '-' in teams_str:
                            parts = teams_str.split('-', 1)
                            team_a = parts[0].strip()
                            team_b = parts[1].strip()
                        elif 'vs' in teams_str.lower():
                            parts = re.split(r'vs', teams_str, flags=re.IGNORECASE)
                            team_a = parts[0].strip()
                            team_b = parts[1].strip() if len(parts) > 1 else ""
                        else:
                            team_a = teams_str
                            team_b = ""
                    else:
                        # Fallback
                        league = "赛事"
                        content_clean = match_text.replace(time_str, "").strip()
                        team_a = re.sub(r'互动直播|手机看直播|视频|文字|比分|动画', '', content_clean).strip()
                        team_b = ""

                    # 4. 构造片段
                    fragment = f'<span class="_league">{league}</span><span class="_teams">{team_a} vs {team_b}</span>'

                    results.append({
                        'id': str(li.get('id') or '').replace('saishi', '').strip(),
                        'provider': 'zhibo8',
                        'provider_id': str(li.get('id') or '').replace('saishi', '').strip(),
                        'raw_time': raw_time,
                        'date': date_str,
                        'time': time_str,
                        'type': game_type, 
                        'content': fragment,
                        'league': league,
                        'team_a': team_a,
                        'team_b': team_b,
                        'team_a_logo': team_a_logo,
                        'team_b_logo': team_b_logo,
                        'media': "视频/互动",
                        'status': 'not_started',
                        'status_known': False,
                        'live': False,
                        'score_a': None,
                        'score_b': None,
                        'period_text': '',
                        'current_game': None,
                        'winner': '',
                    })

            self._enrich_started_matches(results)
            df = pd.DataFrame(results)
            return df
            
        except Exception as e:
            print(f"[GameScraper] Error: {e}")
            return pd.DataFrame()

def get_game_schedule(games):
    return GameSchedule(games)
