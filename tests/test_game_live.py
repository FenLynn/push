from datetime import datetime, timedelta, timezone

from core.utils.lol_esports import normalize_event
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
            {'code': code_a, 'name': code_a, 'image': 'http://img/a.png', 'lightImage': 'http://img/a-white.png', 'result': {'gameWins': 1}},
            {'code': code_b, 'name': code_b, 'image': 'http://img/b.png', 'result': {'gameWins': 0}},
        ],
    }


def test_normalizes_exact_watched_live_match():
    match = normalize_event(_event())
    assert match['live'] is True
    assert match['currentGame'] == 2
    assert match['scoreText'] == '1:0'
    assert match['teamALogo'] == 'https://img/a.png'
    assert match['leagueLogo'] == 'https://img/lck.png'


def test_non_watched_match_is_ignored():
    assert normalize_event(_event('KT', 'DK')) is None


def test_notification_is_once_and_only_near_start():
    now = datetime.now(timezone.utc)
    match = normalize_event(_event(state='unstarted'))
    match['startTime'] = (now + timedelta(minutes=40)).isoformat().replace('+00:00', 'Z')
    assert select_notification_candidates([match], {}, now=now) == [match]
    assert select_notification_candidates([match], {'match-1': now.isoformat()}, now=now) == []
    match['startTime'] = (now + timedelta(hours=3)).isoformat().replace('+00:00', 'Z')
    assert select_notification_candidates([match], {}, now=now) == []
