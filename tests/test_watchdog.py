from datetime import datetime, timedelta, timezone

from core.watchdog import detect_issues, evaluate_alert_state


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
