import sys
import os
import time
import re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sources.base import BaseSource
from core import Message, ContentType
from core.template import TemplateEngine

# 导入原有的 cloud 库
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from cloud import *


class GameSource(BaseSource):
    """游戏赛程数据源 (V2)"""
    
    DEFAULT_GAMES = ['王者荣耀', 'DOTA2', 'S15', 'KPL', '英雄联盟', 'LOL', 'LCK',
                     '欧洲杯', 'TI14', 'LEC', '刀塔', 'LPL', 'PCL', 'S赛', 'TI',
                     '男篮世界杯', '男篮欧锦赛', '欧冠']
    
    HIGHLIGHTED_TEAMS = ['HLE', 'T1', 'GEN', 'BLG']
    
    WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    def __init__(self, topic='me', games=None):
        super().__init__()
        self.topic = topic
        self.games = games or self.DEFAULT_GAMES
        self.template = TemplateEngine()
    
    MAX_MESSAGE_SIZE = 19000  # Increased to 19KB as per user request

    def run(self) -> Message:
        try:
            days_data = self._get_formatted_data()
            # 挑选 Hero Match (推荐赛事)
            hero_match = self._pick_hero_match(days_data)

            # --- Smart Truncation Logic ---
            # Try to fit content into one page by progressively reducing days/matches
            final_content = ""
            
            # Deep copy to allow modification without affecting cache if we had one
            current_data = days_data[:] 
            
            while True:
                # Render current data
                html_content = self.template.render('game.html', {
                    'title': '最新赛程',
                    'date_str': time.strftime("%Y-%m-%d", time.localtime()),
                    'update_time': time.strftime("%H:%M", time.localtime()),
                    'days_data': current_data,
                    'hero_match': hero_match
                })
                
                # Minify
                html_content = re.sub(r'<!--.*?-->', '', html_content, flags=re.DOTALL)
                html_content = re.sub(r'>\s+<', '><', html_content)
                html_content = re.sub(r'\s+', ' ', html_content).strip()
                
                # Check size
                if len(html_content.encode('utf-8')) <= self.MAX_MESSAGE_SIZE:
                    final_content = html_content
                    break
                
                # If too big, reduce data
                if len(current_data) > 1:
                    # Drop the last day
                    current_data.pop()
                elif len(current_data) == 1:
                    # Only one day left, but still too big? Drop last match
                    if len(current_data[0]['matches']) > 0:
                        current_data[0]['matches'].pop()
                    else:
                        # Should not happen (empty day), but break to avoid loop
                        final_content = html_content
                        break
                else:
                    # No data left?
                    final_content = html_content
                    break

            return Message(
                title=f'电竞前线({time.strftime("%m-%d")})',
                content=final_content,
                type=ContentType.HTML,
                tags=['game', 'schedule']
            )
        except Exception as e:
            import traceback
            traceback.print_exc()
            return Message(
                title='Game Error',
                content=f"Error: {str(e)}",
                type=ContentType.TEXT
            )

    def _pick_hero_match(self, days_data):
        """选择今日或次日的焦点赛事"""
        best_match = None
        highest_score = 0
        
        # 优先看今天的，如果不精彩看明天的
        candidates = []
        for day in days_data[:2]: # Look at first 2 days
            for m in day['matches']:
                score = 0
                content = (m['league'] + m['team_a'] + m['team_b']).upper()
                
                # 评分系统
                # 1. 重点战队
                for ht in self.HIGHLIGHTED_TEAMS:
                    if ht in content:
                        score += 10
                
                # 2. 关键阶段
                if '决赛' in content: score += 50
                if '季后赛' in content: score += 20
                if 'S组' in content: score += 15
                if 'LPL' in content or 'LCK' in content: score += 5
                
                if score > 0:
                    candidates.append({'match': m, 'score': score, 'date': day['date_label'], 'weekday': day['weekday']})
        
        if candidates:
            # Sort by score desc
            candidates.sort(key=lambda x: x['score'], reverse=True)
            top = candidates[0]
            # Clean HTML from teams for clean display in Hero section
            m = top['match']
            
            # Helper to strip html tags for header display
            def strip_tags(s):
                return re.sub('<[^<]+?>', '', s)

            return {
                'league': m['league'],
                'time': f"{top['date']} {m['time']}",
                'team_a': strip_tags(m['team_a']),
                'team_b': strip_tags(m['team_b']),
                'type': m['type']
            }
        
        return None

    def _get_formatted_data(self):
        """获取并格式化数据"""
        game_schedule = get_game_schedule(self.games)
        df = game_schedule.get_all_game_info()
        
        if df.empty:
            return []

        # 获取未来6天
        target_dates = [(datetime.now() + timedelta(days=i)).strftime('%Y-%m-%d') for i in range(7)]
        today = datetime.now().strftime('%Y-%m-%d')
        
        res_days = []
        
        # 按日期分组处理
        for date_str in target_dates:
            day_games = df[df['date'] == date_str]
            if day_games.empty:
                continue
                
            matches = []
            for _, row in day_games.iterrows():
                # 解析内容
                league, team_a, team_b = self._parse_content(row['content'])
                
                # 高亮处理 logic
                # 标记整行是否高亮 (用于背景色)
                is_highlight_row = False
                
                # 分别检查 Team A 和 Team B
                # 如果匹配，用 HTML 包装
                for ht in self.HIGHLIGHTED_TEAMS:
                    if ht.upper() in team_a.upper():
                        team_a = team_a.replace(ht, f'<span class="hl-txt">{ht}</span>')
                        is_highlight_row = True
                    if ht.upper() in team_b.upper():
                        team_b = team_b.replace(ht, f'<span class="hl-txt">{ht}</span>')
                        is_highlight_row = True
                
                matches.append({
                    'time': row['time'],
                    'type': row['type'],
                    'league': league,
                    'team_a': team_a, # 包含 HTML
                    'team_b': team_b, # 包含 HTML
                    'media': row['media'],
                    'highlight': is_highlight_row
                })
            
            # 日期标签
            date_obj = datetime.strptime(date_str, "%Y-%m-%d")
            weekday = self.WEEKDAYS[date_obj.weekday()]
            
            label = date_str
            is_today = (date_str == today)
            
            if is_today:
                label = "今天"
            elif date_str == (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d'):
                label = "明天"
            else:
                label = date_obj.strftime("%m-%d")

            res_days.append({
                'date_label': label,
                'weekday': weekday,
                'is_today': is_today,
                'matches': matches
            })
            
        return res_days

    def _parse_content(self, html_content):
        """
        解析 HTML 内容提取 联赛 和 队伍
        Input: <spanclass="_league">LPL第一赛段登峰组</span><spanclass="_teams">IG vs.>WBG  互动直播
        """
        try:
            # 提取 league
            league_match = re.search(r'class="_league">([^<]+)<', html_content)
            league = league_match.group(1) if league_match else ""
            
            # 提取 teams
            teams_match = re.search(r'class="_teams">([^<]+)', html_content)
            raw_teams = teams_match.group(1) if teams_match else ""
            
            # 清理
            clean_teams = raw_teams.replace('>', '').replace('&gt;', '').replace('互动直播', '').strip()
            
            if 'vs.' in clean_teams:
                parts = clean_teams.split('vs.')
            elif 'vs' in clean_teams:
                parts = clean_teams.split('vs')
            else:
                parts = [clean_teams, ""]
                
            team_a = parts[0].strip()
            team_b = parts[1].strip() if len(parts) > 1 else ""
            
            return league, team_a, team_b
            
        except Exception as e:
            print(f"Parse Error: {e}")
            return "", html_content, "" # Fallback

if __name__ == '__main__':
    source = GameSource()
    msg = source.run()
    # Write to a test file to inspect
    with open('test_game_v2.html', 'w') as f:
        f.write(msg.content)
    print("Generated test_game_v2.html")
