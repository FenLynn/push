from datetime import datetime, timedelta, timezone

from core.utils.lol_esports import enrich_live_game_winners, normalize_event
from scripts.notify_game import select_notification_candidates


def _event(code_a='T1', code_b='GEN', state='inProgress'):
    return {
        '__typename': 'EventMatch',
        'id': 'event-1',
        'startTime': '2026-07-18T11:00:00Z',
        'state': state,
        'league': {'name': 'LCK', 'slug': 'lck', 'image': 'http://img/lck.png'},
        'match': {
            'id': 'match-1',
            'state': state,
            'strategy': {'count': 5},
            'games': [
                {'id': 'g1', 'number': 1, 'state': 'completed'},
                {'id': 'g2', 'number': 2, 'state': 'inProgress'},
            ],
        },
        'matchTeams': [
            {'id': f'match-1:team-{code_a}', 'code': code_a, 'name': code_a, 'image': 'http://img/a.png', 'lightImage': 'http://img/a-white.png', 'result': {'gameWins': 1}},
            {'id': f'match-1:team-{code_b}', 'code': code_b, 'name': code_b, 'image': 'http://img/b.png', 'result': {'gameWins': 0}},
        ],
    }


def test_normalizes_exact_watched_live_match():
    match = normalize_event(_event())
    assert match['live'] is True
    assert match['currentGame'] == 2
    assert match['scoreText'] == '1:0'
    assert match['startTime'] == '2026-07-18T11:00:00Z'
    assert match['teamALogo'] == 'https://img/a.png'
    assert match['leagueLogo'] == 'https://img/lck.png'


def test_non_watched_match_is_ignored():
    assert normalize_event(_event('KT', 'DK')) is None


def test_nested_unstarted_state_rejects_false_completed_wrapper():
    event = _event('TT', 'BLG', state='completed')
    event['startTime'] = '2026-07-23T09:00:00Z'
    event['match']['id'] = '116566854547769568'
    event['match']['state'] = 'unstarted'
    event['match']['strategy'] = {'count': 3}
    event['match']['games'] = [
        {'id': 'g1', 'number': 1, 'state': 'unstarted'},
        {'id': 'g2', 'number': 2, 'state': 'unstarted'},
        {'id': 'g3', 'number': 3, 'state': 'unstarted'},
    ]
    event['matchTeams'][0]['result'] = {'gameWins': 0}
    event['matchTeams'][1]['result'] = {'gameWins': 0}

    match = normalize_event(event)

    assert match['status'] == 'unstarted'
    assert match['live'] is False
    assert match['currentGame'] is None
    assert match['scoreA'] is None
    assert match['scoreB'] is None
    assert match['scoreText'] == ''
    assert match['winner'] == ''


def test_team_names_drop_redundant_esports_word():
    event = _event()
    event['matchTeams'][0]['name'] = 'Bilibili Gaming'
    event['matchTeams'][1]['name'] = 'Gen.G Esports'
    event['league']['name'] = 'Esports World Cup'
    match = normalize_event(event)
    assert match['teamA'] == 'Bilibili'
    assert match['teamB'] == 'Gen.G'
    assert match['league'] == 'World Cup'


def test_live_completed_game_winner_uses_official_team_id():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'gameMetadata': {
                    'blueTeamMetadata': {'esportsTeamId': 'team-GEN'},
                    'redTeamMetadata': {'esportsTeamId': 'team-T1'},
                },
                'frames': [{
                    'gameState': 'in_game',
                    'blueTeam': {'towers': 5},
                    'redTeam': {'towers': 11},
                }],
            }

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    match = normalize_event(_event())
    enriched = enrich_live_game_winners(match, datetime.now(timezone.utc), session=Session())
    assert enriched['games'][0]['winner'] == 'T1'
    assert enriched['games'][1]['winner'] == ''


def test_series_score_fills_unresolved_surrendered_game():
    class Response:
        def raise_for_status(self):
            return None

        def json(self):
            return {
                'gameMetadata': {
                    'blueTeamMetadata': {'esportsTeamId': 'team-T1'},
                    'redTeamMetadata': {'esportsTeamId': 'team-GEN'},
                },
                'frames': [{
                    'gameState': 'finished',
                    'blueTeam': {'towers': 7},
                    'redTeam': {'towers': 3},
                }],
            }

    class Session:
        def get(self, *args, **kwargs):
            return Response()

    match = normalize_event(_event())
    enriched = enrich_live_game_winners(match, datetime.now(timezone.utc), session=Session())
    assert enriched['games'][0]['winner'] == 'T1'


def test_notification_is_once_and_only_near_start():
    now = datetime.now(timezone.utc)
    scheduled_event = _event(state='unstarted')
    scheduled_event['match']['games'] = [
        {'id': 'g1', 'number': 1, 'state': 'unstarted'},
        {'id': 'g2', 'number': 2, 'state': 'unstarted'},
    ]
    scheduled_event['matchTeams'][0]['result'] = {'gameWins': 0}
    scheduled_event['matchTeams'][1]['result'] = {'gameWins': 0}
    match = normalize_event(scheduled_event)
    match['startTime'] = (now + timedelta(minutes=40)).isoformat().replace('+00:00', 'Z')
    assert select_notification_candidates([match], {}, now=now) == [match]
    assert select_notification_candidates([match], {'match-1': now.isoformat()}, now=now) == []
    match['startTime'] = (now + timedelta(hours=3)).isoformat().replace('+00:00', 'Z')
    assert select_notification_candidates([match], {}, now=now) == []
