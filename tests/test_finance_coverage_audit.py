import pandas as pd

from scripts.audit_finance_coverage import audit_frame


def test_audit_ignores_empty_future_rows_and_marks_combined_periods_structural():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2025-02-28", "2025-03-31", "2025-06-30", "2025-07-31"]),
        "value": [100, 110, 150, None],
        "period_span": [2, 1, 3, 1],
    })
    result = audit_frame("sample", frame, {
        "frequency": "monthly",
        "metrics": {"value": {"label": "值"}},
    })
    assert result["raw_rows"] == 4
    assert result["rows"] == 3
    assert result["empty_rows"] == 1
    assert result["latest"] == "2025-06-30"
    assert result["period_gaps"] == []
    assert result["structural_gaps"] == ["2025-04", "2025-05"]


def test_audit_does_not_invent_gaps_for_mixed_frequency_group():
    frame = pd.DataFrame({
        "date": pd.to_datetime(["2020-12-31", "2021-12-31", "2024-03-31"]),
        "annual": [100, 110, None],
        "quarter": [None, None, 30],
    })
    result = audit_frame("mixed", frame, {
        "frequency": "quarterly",
        "mixed_frequency": True,
        "metrics": {"annual": {}, "quarter": {}},
    })
    assert result["period_gaps"] == []
