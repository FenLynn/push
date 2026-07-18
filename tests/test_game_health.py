from datetime import datetime

from sources.game.source import GameSource


def test_watched_schedule_matching_uses_team_aliases_not_substrings():
    source = GameSource(topic='me')
    assert source._has_watched_schedule([{
        'matches': [{'team_a': '<span>Gen.G</span>', 'team_b': 'Dplus KIA'}],
    }])
    assert not source._has_watched_schedule([{
        'matches': [{'team_a': 'Oxygen', 'team_b': 'Random Club'}],
    }])


def test_official_match_overrides_snapshot_and_records_nonfatal_conflicts():
    source = GameSource(topic='me')
    today = datetime.now().strftime('%Y-%m-%d')
    days = [{
        'date': today,
        'matches': [{
            'providerId': 'match-1',
            'time': '11:00',
            'team_a': 'T1',
            'team_b': 'Gen.G',
            'score_a': 1,
            'score_b': 1,
            'status': 'running',
        }],
    }]
    official = [{
        'providerId': 'match-1',
        'date': today,
        'time': '12:00',
        'teamA': 'T1',
        'teamB': 'Gen.G',
        'teamACode': 'T1',
        'teamBCode': 'GEN',
        'scoreA': 2,
        'scoreB': 1,
        'status': 'completed',
    }]

    merged = source._merge_official_matches(days, official)
    assert merged[0]['matches'][0]['scoreA'] == 2
    assert merged[0]['matches'][0]['status'] == 'completed'
    assert {item['type'] for item in source._source_diagnostics['conflicts']} == {'scheduled-time', 'score'}

