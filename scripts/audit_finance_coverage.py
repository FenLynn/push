"""Audit every active Finance archive series for coverage and freshness.

This script is read-only. It fetches the same frames used by the Finance
workflow and reports source failures, historical boundaries, internal period
gaps and per-metric non-null coverage. It deliberately does not interpolate or
write anything to D1/R2.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sources.finance.archive_catalog import ARCHIVE_CATALOG
from sources.finance.source import FinanceSource


def _period_key(values: pd.Series, frequency: str) -> pd.PeriodIndex | None:
    aliases = {"annual": "Y", "quarterly": "Q", "monthly": "M"}
    alias = aliases.get(frequency)
    if not alias:
        return None
    return pd.PeriodIndex(pd.to_datetime(values), freq=alias)


def audit_frame(name: str, frame: pd.DataFrame, spec: dict) -> dict:
    result = {
        "group": name,
        "label": spec.get("label", name),
        "source": spec.get("source", ""),
        "frequency": spec.get("frequency", ""),
        "quality": spec.get("quality", "official"),
        "rows": 0,
        "raw_rows": 0,
        "empty_rows": 0,
        "start": None,
        "latest": None,
        "period_gaps": [],
        "metrics": {},
    }
    if not isinstance(frame, pd.DataFrame) or frame.empty or "date" not in frame:
        result["error"] = "collector returned no dated observations"
        return result

    normalized = frame.copy()
    result["raw_rows"] = int(len(normalized))
    normalized["date"] = pd.to_datetime(normalized["date"], errors="coerce")
    normalized = normalized.dropna(subset=["date"]).sort_values("date").drop_duplicates("date", keep="last")
    metric_columns = [metric for metric in (spec.get("metrics") or {}) if metric in normalized]
    if metric_columns:
        numeric = normalized[metric_columns].apply(pd.to_numeric, errors="coerce")
        empty_mask = numeric.isna().all(axis=1)
        result["empty_rows"] = int(empty_mask.sum())
        normalized = normalized.loc[~empty_mask].copy()
    if normalized.empty:
        result["error"] = "collector returned no non-empty dated observations"
        return result

    result["rows"] = int(len(normalized))
    result["start"] = normalized["date"].iloc[0].date().isoformat()
    result["latest"] = normalized["date"].iloc[-1].date().isoformat()
    # Some groups intentionally combine two publication cadences (for
    # example annual marriage totals plus quarterly releases). A single
    # PeriodIndex would turn the pre-quarterly years into false data holes.
    periods = None if spec.get("mixed_frequency") else _period_key(
        normalized["date"], str(spec.get("frequency") or "")
    )
    if periods is not None and len(periods):
        expected = pd.period_range(periods.min(), periods.max(), freq=periods.freq)
        missing = expected.difference(periods.unique())
        explained = set()
        if str(spec.get("frequency") or "") == "monthly" and "period_span" in normalized:
            for _, row in normalized[["date", "period_span"]].dropna().iterrows():
                span = int(row["period_span"])
                end = pd.Period(row["date"], freq="M")
                explained.update(end - offset for offset in range(1, max(1, span)))
        result["period_gaps"] = [str(item) for item in missing if item not in explained]
        result["structural_gaps"] = [str(item) for item in missing if item in explained]

    for metric, metric_spec in (spec.get("metrics") or {}).items():
        if metric not in normalized:
            result["metrics"][metric] = {
                "label": metric_spec.get("label", metric),
                "present": False,
                "observations": 0,
                "start": None,
                "latest": None,
            }
            continue
        values = pd.to_numeric(normalized[metric], errors="coerce")
        dated = normalized.loc[values.notna(), ["date"]]
        result["metrics"][metric] = {
            "label": metric_spec.get("label", metric),
            "present": True,
            "observations": int(values.notna().sum()),
            "start": dated["date"].iloc[0].date().isoformat() if not dated.empty else None,
            "latest": dated["date"].iloc[-1].date().isoformat() if not dated.empty else None,
            "quality": metric_spec.get("quality", result["quality"]),
        }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--groups", default="", help="comma-separated group names")
    parser.add_argument("--output", default="", help="optional JSON output path")
    parser.add_argument("--summary-only", action="store_true", help="do not print the full JSON payload")
    args = parser.parse_args()
    requested = {item.strip().lower() for item in args.groups.split(",") if item.strip()}

    source = FinanceSource()
    active = {indicator.name: indicator for indicator in source.indicators}
    names = [name for name in ARCHIVE_CATALOG if name in active and (not requested or name in requested)]
    report = []
    for name in names:
        spec = ARCHIVE_CATALOG[name]
        try:
            frame = active[name].fetch_data()
            item = audit_frame(name, frame, spec)
        except Exception as exc:  # audit must continue after one failing source
            item = {
                "group": name,
                "label": spec.get("label", name),
                "source": spec.get("source", ""),
                "frequency": spec.get("frequency", ""),
                "quality": spec.get("quality", "official"),
                "error": f"{type(exc).__name__}: {exc}",
            }
        report.append(item)
        status = item.get("error") or f"{item['start']} -> {item['latest']} ({item['rows']} rows)"
        print(f"[{name}] {status}", flush=True)

    payload = {"generated_at": pd.Timestamp.now(tz="Asia/Shanghai").isoformat(), "groups": report}
    if args.output:
        target = Path(args.output)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    if not args.summary_only:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 1 if any(item.get("error") for item in report) else 0


if __name__ == "__main__":
    raise SystemExit(main())
