from datetime import datetime, timedelta, timezone

from core.watchdog import detect_game_snapshot_issues, detect_issues, evaluate_alert_state


NOW = datetime(2026, 7, 18, 8, 0, tzinfo=timezone.utc)


def _run(name, hours_ago, conclusion='success'):
    started = NOW - timedelta(hours=hours_ago)
    return {
        'name': name,
        'status': 'completed',
        'conclusion': conclusion,
        'run_started_at': started.isoformat().replace('+00:00', 'Z'),
    }


def test_latest_success_clears_an_older_failure():
    issues = detect_issues([_run('Module: Game Schedule', 3, 'failure'), _run('Module: Game Schedule', 1, 'success')], now=NOW)
    assert 'workflow:Module: Game Schedule' not in issues


def test_failure_is_recorded_but_not_alerted_before_48_hours():
    issues = {'workflow:game': 'game failed'}
    state, due = evaluate_alert_state({}, issues, now=NOW)
    assert due == []
    state, due = evaluate_alert_state(state, issues, now=NOW + timedelta(hours=47))
    assert due == []
    state, due = evaluate_alert_state(state, issues, now=NOW + timedelta(hours=48))
    assert due == [('workflow:game', 'game failed')]
    state['issues']['workflow:game']['notifiedAt'] = (NOW + timedelta(hours=48)).isoformat()
    _, repeated = evaluate_alert_state(state, issues, now=NOW + timedelta(hours=72))
    assert repeated == []


def test_resolved_issue_is_removed_and_will_start_a_new_window():
    state, _ = evaluate_alert_state({}, {'workflow:game': 'game failed'}, now=NOW)
    cleared, due = evaluate_alert_state(state, {}, now=NOW + timedelta(hours=12))
    assert cleared['issues'] == {}
    assert due == []


def test_game_snapshot_health_and_staleness_are_detected():
    snapshot = {
        'generatedAt': (NOW - timedelta(hours=21)).isoformat().replace('+00:00', 'Z'),
        'payload': {
            'health': {
                'status': 'warning',
                'issues': [{'code': 'official-source-unavailable', 'message': 'official timeout'}],
            },
        },
    }
    issues = detect_game_snapshot_issues(snapshot, now=NOW)
    assert 'game:snapshot-stale' in issues
    assert issues['game:official-source-unavailable'].endswith('official timeout')


def test_game_health_issue_still_uses_the_48_hour_alert_window():
    issues = detect_game_snapshot_issues({
        'generatedAt': NOW.isoformat().replace('+00:00', 'Z'),
        'payload': {'health': {'issues': [{'code': 'final-score-missing', 'message': 'missing'}]}},
    }, now=NOW)
    state, due = evaluate_alert_state({}, issues, now=NOW)
    assert due == []
    _, due = evaluate_alert_state(state, issues, now=NOW + timedelta(hours=48))
    assert due == [('game:final-score-missing', '赛事数据健康检查：missing')]
