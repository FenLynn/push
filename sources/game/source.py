import sys
import os
import time
import re
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from sources.base import BaseSource
from core import Message, ContentType
from core.template import TemplateEngine
from core.dashboard_snapshot import export_dashboard_snapshot
from core.utils.lol_esports import WATCHED_TEAM_CODES, fetch_watched_matches

# 导入原有的 cloud 库
sys.path.append(os.path.join(os.path.dirname(__file__), '../..'))
from core.legacy import *
import pandas as pd



class GameSource(BaseSource):
    """游戏赛程数据源 (V2)"""
    
    DEFAULT_GAMES = ['世界杯','王者荣耀', 'DOTA2', 'S16', 'KPL', '英雄联盟', 'LOL', 'LCK',
                     '欧洲杯', 'TI14', 'LEC', '刀塔', 'LPL', 'PCL', 'S赛', 'TI',
                     '男篮世界杯', '男篮欧锦赛', '欧冠','MSI']
    
    HIGHLIGHTED_TEAMS = list(WATCHED_TEAM_CODES)
    WATCHED_TEAM_ALIASES = {
        'T1': {'T1', 'SKTT1', 'SKTELECOMT1'},
        'HLE': {'HLE', 'HANWHALIFE', 'HANWHALIFEESPORTS'},
        'GEN': {'GEN', 'GENG', 'GENGESPORTS'},
        'BLG': {'BLG', 'BILIBILI', 'BILIBILIGAMING'},
    }

    # 首页和小程序共享同一份赛程快照。LOL 只发布一级联赛和国际大赛，
    # 避免宽泛的 “LOL” 抓取词把 LJL、学院及次级联赛全部带入前端。
    LOL_MAJOR_EVENT_KEYWORDS = (
        'LPL', 'LCK', 'LEC', 'LCS', 'LTA', 'LCP',
        'MSI', 'MID-SEASON', '季中冠军',
        'WORLD CHAMPIONSHIP', 'WORLDS', '全球总决赛', 'S赛',
        'ESPORTS WORLD CUP', 'EWC', '电竞世界杯',
        'FIRST STAND', '先锋赛', '亚运会',
    )
    LOL_DEVELOPMENT_EVENT_KEYWORDS = (
        'LJL', 'LDL', 'LCK CL', 'LCK CHALLENGERS',
        'ACADEMY', 'CHALLENGERS', 'DEVELOPMENT',
        '学院', '次级', '发展联赛', '青训',
    )
    
    WEEKDAYS = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"]
    
    def __init__(self, topic='me', games=None, **kwargs):
        super().__init__(**kwargs)
        self.topic = topic
        self.games = games or self.DEFAULT_GAMES
        self.template = TemplateEngine()
        self._official_error = ''
        self._source_diagnostics = {}
    
    MAX_MESSAGE_SIZE = 19000  # Increased to 19KB as per user request

    def run(self) -> Message:
        try:
            days_data = self._get_formatted_data()
            official_matches = self._get_official_lol_matches()
            days_data = self._merge_official_matches(days_data, official_matches)
            checked_at = datetime.now().astimezone().isoformat()
            health = self._build_health(days_data, official_matches, checked_at)
            # 挑选 Hero Match (推荐赛事)
            hero_match = self._pick_hero_match(days_data)
            total_matches = sum(len(day.get('matches', [])) for day in days_data)
            export_dashboard_snapshot('game', {
                'heroMatch': hero_match,
                'days': days_data,
                'totalDays': len(days_data),
                'totalMatches': total_matches,
                'highlightedTeams': self.HIGHLIGHTED_TEAMS,
                'watchedTeams': self.HIGHLIGHTED_TEAMS,
                'liveMatches': [match for match in official_matches if match.get('live')],
                'hasLive': any(match.get('live') for match in official_matches),
                'liveSource': 'LOL Official' if official_matches else 'schedule-fallback',
                'liveUpdatedAt': checked_at if official_matches else '',
                'liveError': self._official_error,
                'sourceDiagnostics': self._source_diagnostics,
                'health': health,
            })

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
            export_dashboard_snapshot('game', {
                'heroMatch': None,
                'days': [],
                'totalDays': 0,
                'totalMatches': 0,
                'highlightedTeams': self.HIGHLIGHTED_TEAMS,
                'watchedTeams': self.HIGHLIGHTED_TEAMS,
                'error': str(e),
                'health': {
                    'status': 'warning',
                    'checkedAt': datetime.now().astimezone().isoformat(),
                    'issues': [{'code': 'game-pipeline-error', 'message': str(e)}],
                },
            })
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
                    candidates.append({
                        'match': m,
                        'score': score,
                        'date': day.get('date', ''),
                        'date_label': day['date_label'],
                        'weekday': day['weekday']
                    })
        
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
                'time': f"{top['date_label']} {m['time']}",
                'date': top.get('date', ''),
                'date_label': top.get('date_label', ''),
                'weekday': top.get('weekday', ''),
                'team_a': strip_tags(m['team_a']),
                'team_b': strip_tags(m['team_b']),
                'type': m['type']
            }
        
        return None

    def _get_official_lol_matches(self):
        try:
            matches = fetch_watched_matches()
            self._official_error = ''
            return matches
        except Exception as exc:
            self._official_error = str(exc)
            self.logger.warning('LoL Esports live data unavailable; keeping schedule fallback: %s', exc)
            return []

    @staticmethod
    def _plain_team(value):
        return re.sub(r'<[^>]*>', '', str(value or '')).strip().upper()

    @classmethod
    def _team_key(cls, value):
        return re.sub(r'[^A-Z0-9]', '', cls._plain_team(value))

    @classmethod
    def _is_watched_team(cls, value):
        key = cls._team_key(value)
        return any(key in aliases for aliases in cls.WATCHED_TEAM_ALIASES.values())

    @classmethod
    def _should_publish_match(cls, game_type, league, team_a='', team_b=''):
        """Keep the public schedule useful without hiding followed teams."""
        if cls._is_watched_team(team_a) or cls._is_watched_team(team_b):
            return True
        league_text = str(league or '').strip().upper()
        if any(keyword.upper() in league_text for keyword in cls.LOL_DEVELOPMENT_EVENT_KEYWORDS):
            return False
        if str(game_type or '').strip().upper() != 'LOL':
            return True
        return any(keyword.upper() in league_text for keyword in cls.LOL_MAJOR_EVENT_KEYWORDS)

    def _has_watched_schedule(self, days_data):
        for day in days_data:
            for match in day.get('matches') or []:
                if self._is_watched_team(match.get('team_a')) or self._is_watched_team(match.get('team_b')):
                    return True
        return False

    def _build_health(self, days_data, official_matches, checked_at):
        issues = []
        if self._official_error:
            issues.append({'code': 'official-source-unavailable', 'message': self._official_error})
        elif not official_matches and self._has_watched_schedule(days_data):
            issues.append({
                'code': 'official-watched-matches-missing',
                'message': '赛程中存在关注队伍，但官方 LoL 数据未返回对应比赛',
            })
        for match in official_matches:
            if str(match.get('status') or '').lower() in ('completed', 'complete', 'finished'):
                score_a = match.get('scoreA')
                score_b = match.get('scoreB')
                if score_a in (None, '') or score_b in (None, '') or (score_a == 0 and score_b == 0):
                    issues.append({
                        'code': 'final-score-missing',
                        'message': f"{match.get('teamACode') or match.get('teamA')} vs {match.get('teamBCode') or match.get('teamB')} 已结束但缺少有效比分",
                    })
        severe_conflicts = [
            item for item in self._source_diagnostics.get('conflicts', [])
            if item.get('severity') == 'error'
        ]
        if severe_conflicts:
            issues.append({
                'code': 'source-identity-conflict',
                'message': f"双源存在 {len(severe_conflicts)} 个队伍身份冲突",
            })
        return {
            'status': 'warning' if issues else 'ok',
            'checkedAt': checked_at,
            'issues': issues,
        }

    def _merge_official_matches(self, days_data, official_matches):
        """Replace duplicate watched LoL rows and append missing official matches."""
        diagnostics = {
            'checkedAt': datetime.now().astimezone().isoformat(),
            'officialCount': len(official_matches),
            'matchedCount': 0,
            'appendedCount': 0,
            'conflictCount': 0,
            'conflicts': [],
        }
        by_date = {str(day.get('date') or ''): {**day, 'matches': list(day.get('matches') or [])} for day in days_data}
        today = datetime.now().strftime('%Y-%m-%d')
        for match in official_matches:
            if not match.get('date'):
                continue
            if match.get('status') == 'completed' and match.get('date') != today:
                continue
            date_str = match['date']
            day = by_date.get(date_str)
            if not day:
                date_obj = datetime.strptime(date_str, '%Y-%m-%d')
                day = {
                    'date': date_str,
                    'date_label': '今天' if date_str == today else date_obj.strftime('%m-%d'),
                    'weekday': self.WEEKDAYS[date_obj.weekday()],
                    'is_today': date_str == today,
                    'matches': [],
                }

            normalized = {
                **match,
                'team_a': match.get('teamA', ''),
                'team_b': match.get('teamB', ''),
                'team_a_logo': match.get('teamALogo', ''),
                'team_b_logo': match.get('teamBLogo', ''),
                'team_a_code': match.get('teamACode', ''),
                'team_b_code': match.get('teamBCode', ''),
                'type': 'LOL',
                'media': 'LOL',
                'highlight': True,
            }
            duplicate_index = -1
            for index, old in enumerate(day['matches']):
                old_id = str(old.get('providerId') or old.get('id') or '')
                if old_id and old_id == match.get('providerId'):
                    duplicate_index = index
                    break
                old_teams = (str(old.get('team_a') or '').upper(), str(old.get('team_b') or '').upper())
                codes = (str(match.get('teamACode') or ''), str(match.get('teamBCode') or ''))
                if all(any(code and code in team for team in old_teams) for code in codes):
                    duplicate_index = index
                    break
            if duplicate_index >= 0:
                old = day['matches'][duplicate_index]
                diagnostics['matchedCount'] += 1
                old_id = str(old.get('providerId') or old.get('provider_id') or old.get('id') or '')
                if old_id and old_id == str(match.get('providerId') or ''):
                    old_teams = {self._plain_team(old.get('team_a')), self._plain_team(old.get('team_b'))}
                    official_teams = {self._plain_team(match.get('teamA')), self._plain_team(match.get('teamB'))}
                    if all(old_teams) and all(official_teams) and old_teams.isdisjoint(official_teams):
                        diagnostics['conflicts'].append({
                            'type': 'team-identity',
                            'severity': 'error',
                            'providerId': match.get('providerId'),
                            'message': '同一比赛 ID 的队伍信息不一致',
                        })
                old_time = re.match(r'^(\d{1,2}):(\d{2})', str(old.get('time') or ''))
                official_time = re.match(r'^(\d{1,2}):(\d{2})', str(match.get('time') or ''))
                time_gap = None
                if old_time and official_time:
                    old_minutes = int(old_time.group(1)) * 60 + int(old_time.group(2))
                    official_minutes = int(official_time.group(1)) * 60 + int(official_time.group(2))
                    time_gap = min(abs(old_minutes - official_minutes), 24 * 60 - abs(old_minutes - official_minutes))
                if time_gap is not None and time_gap > 15:
                    diagnostics['conflicts'].append({
                        'type': 'scheduled-time',
                        'severity': 'info',
                        'providerId': match.get('providerId'),
                        'message': '赛程时间与官方源不一致',
                    })
                old_scores = (old.get('score_a'), old.get('score_b'))
                official_scores = (match.get('scoreA'), match.get('scoreB'))
                if all(value is not None for value in old_scores + official_scores) and old_scores != official_scores:
                    diagnostics['conflicts'].append({
                        'type': 'score',
                        'severity': 'info',
                        'providerId': match.get('providerId'),
                        'message': '快照比分落后于官方源',
                    })
                day['matches'][duplicate_index] = {**old, **normalized}
            else:
                diagnostics['appendedCount'] += 1
                day['matches'].append(normalized)
            day['matches'].sort(key=lambda item: str(item.get('time') or ''))
            by_date[date_str] = day
        diagnostics['conflicts'] = diagnostics['conflicts'][:20]
        diagnostics['conflictCount'] = len(diagnostics['conflicts'])
        self._source_diagnostics = diagnostics
        return sorted(by_date.values(), key=lambda day: str(day.get('date') or ''))

    def _get_formatted_data(self):
        """获取并格式化数据"""
        game_schedule = get_game_schedule(self.games)
        df = game_schedule.get_all_game_info()
        
        if df.empty:
            return []

        today = datetime.now().strftime('%Y-%m-%d')
        target_dates = sorted(
            {
                str(value)
                for value in df['date'].dropna().astype(str).tolist()
                if str(value) >= today
            }
        )
        
        res_days = []
        
        # 按抓取结果中的全部未来日期分组处理
        for date_str in target_dates:
            day_games = df[df['date'] == date_str]
            if day_games.empty:
                continue
                
            matches = []
            for _, row in day_games.iterrows():
                def row_value(key, default=None):
                    value = row.get(key, default)
                    return default if pd.isna(value) else value

                # 获取内容
                if 'league' in row and 'team_a' in row and 'team_b' in row:
                    league = row.get('league', '')
                    team_a = row.get('team_a', '')
                    team_b = row.get('team_b', '')
                else:
                    league, team_a, team_b = self._parse_content(row.get('content', ''))

                if not self._should_publish_match(row.get('type'), league, team_a, team_b):
                    continue
                
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
                    'id': row_value('id', ''),
                    'provider': row_value('provider', ''),
                    'provider_id': row_value('provider_id', ''),
                    'time': row['time'],
                    'type': row['type'],
                    'league': league,
                    'team_a': team_a, # 包含 HTML
                    'team_b': team_b, # 包含 HTML
                    'team_a_logo': row.get('team_a_logo', ''),
                    'team_b_logo': row.get('team_b_logo', ''),
                    'media': row['media'],
                    'highlight': is_highlight_row,
                    'status': row_value('status', 'not_started'),
                    'status_known': bool(row_value('status_known', False)),
                    'live': bool(row_value('live', False)),
                    'score_a': row_value('score_a'),
                    'score_b': row_value('score_b'),
                    'period_text': row_value('period_text', ''),
                    'current_game': row_value('current_game'),
                    'winner': row_value('winner', ''),
                })
            
            if not matches:
                continue

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
                'date': date_str,
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
            
            # 使用非贪婪匹配完整抽取 teams 区块
            teams_match = re.search(r'class="_teams">(.*?)</span>', html_content)
            if not teams_match:
                # Fallback to older html end patterns
                teams_match = re.search(r'class="_teams">(.*)', html_content)
            raw_teams = teams_match.group(1) if teams_match else ""
            
            # 回归 bak 逻辑清洗
            clean_teams = re.sub(r'<[^>]+>', '', raw_teams) # 剥离所有 HTML 内置标签
            clean_teams = clean_teams.replace('&gt;', '').replace('互动直播', '').strip()
            
            # 安全的通过含空格的 vs 拆分队伍名
            if ' vs. ' in clean_teams:
                parts = clean_teams.split(' vs. ')
            elif ' vs ' in clean_teams:
                parts = clean_teams.split(' vs ')
            elif ' VS ' in clean_teams:
                parts = clean_teams.split(' VS ')
            elif 'VS' in clean_teams:
                parts = clean_teams.split('VS')
            elif 'vs.' in clean_teams:
                parts = clean_teams.split('vs.')
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
