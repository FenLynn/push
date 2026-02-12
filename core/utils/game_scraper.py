
import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re

class GameSchedule:
    """直播8 (zhibo8.cc) 赛程抓取器"""
    
    URL = "https://www.zhibo8.cc/"
    HEADERS = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36",
        "Referer": "https://www.zhibo8.cc/"
    }

    def __init__(self, target_keywords=None):
        self.target_keywords = target_keywords or []

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
                    type_keywords = {
                        '王者': '王者', 'KPL': '王者',
                        'LOL': 'LOL', 'LPL': 'LOL', 'LCK': 'LOL', '英雄联盟': 'LOL',
                        'DOTA2': 'Dota2', 'DOTA': 'Dota2', '刀塔': 'Dota2',
                        '乒乓': '乒乓', '足球': '足球', '篮球': '篮球', '网球': '网球',
                        '世界杯': '足球', '五大联赛': '足球'
                    }
                    for kw, val in type_keywords.items():
                        if kw.upper() in match_text.upper():
                            game_type = val
                            break
                    
                    # 2. 精准拆分联赛和队伍
                    content_clean = match_text.replace(time_str, "").strip()
                    content_clean = re.sub(r'互动直播|手机看直播|视频|文字|比分|动画|虎牙|咪咕|央视频', '', content_clean).strip()
                    
                    league = "赛事"
                    team_a = ""
                    team_b = ""

                    # 常用赛事前缀
                    common_leagues = ['KPL春季赛', 'LCK杯', 'LPL', 'DOTA2', '斯诺克', '足球', '篮球', '乒乓球']
                    found_league = False
                    for cl in common_leagues:
                        if cl in content_clean:
                            league = cl
                            parts_str = content_clean.split(cl, 1)[-1].strip()
                            if '-' in parts_str:
                                teams_p = parts_str.split('-', 1)
                                team_a = teams_p[0].strip()
                                team_b = teams_p[1].strip()
                            else:
                                team_a = parts_str
                            found_league = True
                            break
                    
                    if not found_league:
                        if '-' in content_clean:
                            parts_str = content_clean.split('-', 1)
                            team_a = parts_str[0].strip()
                            team_b = parts_str[1].strip()
                        else:
                            team_a = content_clean

                    # 4. 优化：在赛事性质关键词（如第二轮A组）后强制增加两个空格
                    # 这里识别复杂的阶段组合
                    stage_pattern = r'(常规赛|季后赛|淘汰赛|决赛|半决赛|1/4决赛|资格赛|第一轮|第二轮|第三轮|第四轮|[A-DS]组)+'
                    match_stage = re.search(stage_pattern, team_a)
                    if match_stage:
                        matched_str = match_stage.group(0)
                        remaining = team_a[len(matched_str):].strip()
                        if remaining:
                            team_a = f"{matched_str}  {remaining}"

                    # 3. 构造片段
                    fragment = f'<span class="_league">{league}</span><span class="_teams">{team_a} vs {team_b}</span>'

                    results.append({
                        'date': date_str,
                        'time': time_str,
                        'type': game_type, 
                        'content': fragment,
                        'media': "视频/互动"
                    })
            
            df = pd.DataFrame(results)
            return df
            
        except Exception as e:
            print(f"[GameScraper] Error: {e}")
            return pd.DataFrame()

def get_game_schedule(games):
    return GameSchedule(games)
