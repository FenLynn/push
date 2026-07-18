from core.utils.game_scraper import normalize_score_payload


def test_normalizes_running_series_score():
    result = normalize_score_payload({
        'state': '2',
        'period_cn': '第3局 12:30',
        'left': {'score': '1'},
        'right': {'score': '1'},
    }, {'team_a': 'T1', 'team_b': 'GEN'})

    assert result['status'] == 'running'
    assert result['live'] is True
    assert result['score_a'] == 1
    assert result['score_b'] == 1
    assert result['current_game'] == 3
    assert result['winner'] == ''


def test_normalizes_finished_score_and_winner():
    result = normalize_score_payload({
        'state': '3',
        'period_cn': '完赛',
        'left': {'score': '3'},
        'right': {'score': '1'},
    }, {'team_a': 'BLG', 'team_b': 'GEN'})

    assert result['status'] == 'finished'
    assert result['live'] is False
    assert result['winner'] == 'BLG'


def test_unknown_state_is_not_guessed():
    assert normalize_score_payload({
        'state': '0',
        'left': {'score': '0'},
        'right': {'score': '0'},
    }) == {}
