"""Normalized, bounded D1 archive for Finance and Estate observations."""

from __future__ import annotations

import datetime as dt
import logging
import math
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

import pandas as pd

from core.d1_client import D1Client


SCHEMA_STATEMENTS = (
    """
    CREATE TABLE IF NOT EXISTS data_series (
        id TEXT PRIMARY KEY,
        domain TEXT NOT NULL,
        group_name TEXT NOT NULL,
        label TEXT NOT NULL,
        location TEXT NOT NULL DEFAULT '',
        metric TEXT NOT NULL,
        frequency TEXT NOT NULL,
        unit TEXT NOT NULL DEFAULT '',
        source TEXT NOT NULL,
        quality TEXT NOT NULL DEFAULT 'observed',
        updated_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_observations (
        series_id TEXT NOT NULL,
        observed_on TEXT NOT NULL,
        resolution TEXT NOT NULL,
        value REAL NOT NULL,
        source_date TEXT,
        quality TEXT NOT NULL DEFAULT 'observed',
        collected_at TEXT NOT NULL,
        PRIMARY KEY (series_id, observed_on, resolution),
        FOREIGN KEY (series_id) REFERENCES data_series(id) ON DELETE CASCADE
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS data_collection_runs (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        domain TEXT NOT NULL,
        collector TEXT NOT NULL,
        status TEXT NOT NULL,
        row_count INTEGER NOT NULL DEFAULT 0,
        detail TEXT,
        created_at TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_data_series_domain ON data_series(domain, group_name, location)",
    "CREATE INDEX IF NOT EXISTS idx_data_observations_lookup ON data_observations(series_id, resolution, observed_on DESC)",
    "CREATE INDEX IF NOT EXISTS idx_data_collection_runs_created ON data_collection_runs(created_at DESC)",
)


def _slug(value: Any) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", str(value or "").strip().lower()).strip("_")
    return normalized or "all"


def _iso_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _date_text(value: Any) -> Optional[str]:
    try:
        parsed = pd.to_datetime(value, errors="coerce")
        if pd.isna(parsed):
            return None
        return parsed.strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError):
        return None


def _query_rows(result: Mapping[str, Any]) -> List[Dict[str, Any]]:
    if not result.get("success"):
        return []
    blocks = result.get("data") or []
    if isinstance(blocks, list) and blocks and isinstance(blocks[0], dict):
        rows = blocks[0].get("results")
        return rows if isinstance(rows, list) else []
    return []


class DataArchive:
    """Persist only canonical observations and enforce rolling retention."""

    DAILY_RETENTION_DAYS = {"finance": 730, "estate": 1095}

    def __init__(self, client: Optional[D1Client] = None):
        self.client = client or D1Client()
        self.enabled = bool(self.client.enabled)
        self.logger = logging.getLogger("Push.DataArchive")
        self._schema_ready = False

    def ensure_schema(self) -> bool:
        if not self.enabled:
            return False
        if self._schema_ready:
            return True
        for statement in SCHEMA_STATEMENTS:
            result = self.client.query(statement.strip())
            if not result.get("success"):
                self.logger.error("D1 archive schema initialization failed: %s", result.get("error"))
                return False
        self._schema_ready = True
        return True

    def _upsert_series(self, metadata: Mapping[str, Any]) -> bool:
        result = self.client.query(
            """
            INSERT INTO data_series
              (id, domain, group_name, label, location, metric, frequency, unit, source, quality, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              label=excluded.label,
              frequency=excluded.frequency,
              unit=excluded.unit,
              source=excluded.source,
              quality=excluded.quality,
              updated_at=excluded.updated_at
            """,
            [
                metadata["id"], metadata["domain"], metadata["group_name"], metadata["label"],
                metadata.get("location", ""), metadata["metric"], metadata["frequency"],
                metadata.get("unit", ""), metadata["source"], metadata.get("quality", "observed"),
                _iso_now(),
            ],
        )
        return bool(result.get("success"))

    def _upsert_observations(self, rows: Iterable[Mapping[str, Any]]) -> int:
        rows = list(rows)
        saved = 0
        for offset in range(0, len(rows), 14):
            batch = rows[offset:offset + 14]
            placeholders = ",".join(["(?, ?, ?, ?, ?, ?, ?)"] * len(batch))
            params: List[Any] = []
            for row in batch:
                params.extend([
                    row["series_id"], row["observed_on"], row["resolution"], row["value"],
                    row.get("source_date"), row.get("quality", "observed"), row["collected_at"],
                ])
            result = self.client.query(
                f"""
                INSERT INTO data_observations
                  (series_id, observed_on, resolution, value, source_date, quality, collected_at)
                VALUES {placeholders}
                ON CONFLICT(series_id, observed_on, resolution) DO UPDATE SET
                  value=excluded.value,
                  source_date=excluded.source_date,
                  quality=excluded.quality,
                  collected_at=excluded.collected_at
                """,
                params,
            )
            if result.get("success"):
                saved += len(batch)
            else:
                self.logger.error("D1 observation batch failed: %s", result.get("error"))
        return saved

    def store_dataframe(
        self,
        *,
        domain: str,
        group_name: str,
        frame: pd.DataFrame,
        metrics: Mapping[str, Mapping[str, Any]],
        label: str,
        source: str,
        frequency: str,
        location: str = "",
        quality: str = "observed",
        date_column: str = "date",
        replace_observations: bool = False,
    ) -> int:
        if frame is None or frame.empty or date_column not in frame.columns or not self.ensure_schema():
            return 0

        working = frame.copy()
        working[date_column] = pd.to_datetime(working[date_column], errors="coerce")
        working = working.dropna(subset=[date_column]).sort_values(date_column)
        collected_at = _iso_now()
        saved = 0

        for column, spec in metrics.items():
            if column not in working.columns:
                continue
            values = pd.to_numeric(working[column], errors="coerce")
            series_frame = pd.DataFrame({"date": working[date_column], "value": values}).dropna()
            series_frame = series_frame.drop_duplicates(subset=["date"], keep="last")
            if series_frame.empty:
                continue

            scale = float(spec.get("scale", 1) or 1)
            series_frame["value"] = series_frame["value"] * scale
            series_frame = series_frame[series_frame["value"].map(lambda value: math.isfinite(float(value)))]
            series_id = ".".join([_slug(domain), _slug(group_name), _slug(location), _slug(column)])
            series_label = str(spec.get("label") or f"{label} {column}").strip()
            metadata = {
                "id": series_id,
                "domain": domain,
                "group_name": group_name,
                "label": series_label,
                "location": location,
                "metric": column,
                "frequency": frequency,
                "unit": str(spec.get("unit") or ""),
                "source": source,
                "quality": quality,
            }
            if not self._upsert_series(metadata):
                continue

            observation_frames = [(frequency, series_frame, quality)]
            if frequency == "daily":
                retention_days = self.DAILY_RETENTION_DAYS.get(domain, 730)
                cutoff = pd.Timestamp.now().normalize() - pd.Timedelta(days=retention_days)
                daily = series_frame[series_frame["date"] >= cutoff]
                monthly = (
                    series_frame.set_index("date")["value"]
                    .resample("MS").mean().dropna().reset_index()
                )
                observation_frames = [("daily", daily, quality), ("monthly", monthly, "rollup")]

            rows = []
            for resolution, observations, observation_quality in observation_frames:
                for item in observations.itertuples(index=False):
                    observed_on = _date_text(item.date)
                    if not observed_on:
                        continue
                    rows.append({
                        "series_id": series_id,
                        "observed_on": observed_on,
                        "resolution": resolution,
                        "value": float(item.value),
                        "source_date": observed_on,
                        "quality": observation_quality,
                        "collected_at": collected_at,
                    })
            series_saved = self._upsert_observations(rows)
            saved += series_saved
            if replace_observations and series_saved == len(rows):
                # Source migrations (for example stale event calendars to
                # official sparse decisions) must remove observations that no
                # longer exist. Delete only after the replacement batch has
                # been written successfully, identified by this run's unique
                # collected_at timestamp.
                self.client.query(
                    "DELETE FROM data_observations WHERE series_id = ? AND collected_at <> ?",
                    [series_id, collected_at],
                )

        self.record_run(domain, group_name, "success" if saved else "empty", saved)
        return saved

    def store_points(self, domain: str, group_name: str, points: Iterable[Mapping[str, Any]], source: str) -> int:
        if not self.ensure_schema():
            return 0
        saved = 0
        for point in points:
            frame = pd.DataFrame([{
                "date": point.get("sourceDate") or point.get("date"),
                "value": point.get("value"),
            }])
            saved += self.store_dataframe(
                domain=domain,
                group_name=group_name,
                frame=frame,
                metrics={"value": {"label": point.get("label") or point.get("category"), "unit": point.get("unit", "")}},
                label=str(point.get("label") or point.get("category") or group_name),
                source=str(point.get("source") or source),
                frequency="daily",
                location=str(point.get("city") or ""),
                quality=str(point.get("quality") or "observed"),
            )
        return saved

    def record_run(self, domain: str, collector: str, status: str, row_count: int, detail: str = "") -> None:
        if not self.ensure_schema():
            return
        self.client.query(
            "INSERT INTO data_collection_runs (domain, collector, status, row_count, detail, created_at) VALUES (?, ?, ?, ?, ?, ?)",
            [domain, collector, status, int(row_count), detail[:500], _iso_now()],
        )

    def run_retention(self) -> None:
        if not self.ensure_schema():
            return
        for domain, days in self.DAILY_RETENTION_DAYS.items():
            cutoff = (dt.date.today() - dt.timedelta(days=days)).isoformat()
            self.client.query(
                """
                INSERT INTO data_observations
                  (series_id, observed_on, resolution, value, source_date, quality, collected_at)
                SELECT o.series_id, substr(o.observed_on, 1, 7) || '-01', 'monthly', AVG(o.value),
                       MAX(o.source_date), 'rollup', MAX(o.collected_at)
                FROM data_observations o
                JOIN data_series s ON s.id = o.series_id
                WHERE s.domain = ? AND o.resolution = 'daily' AND o.observed_on < ?
                GROUP BY o.series_id, substr(o.observed_on, 1, 7)
                ON CONFLICT(series_id, observed_on, resolution) DO UPDATE SET
                  value=excluded.value, source_date=excluded.source_date,
                  quality=excluded.quality, collected_at=excluded.collected_at
                """,
                [domain, cutoff],
            )
            self.client.query(
                """
                DELETE FROM data_observations
                WHERE resolution='daily' AND observed_on < ?
                  AND series_id IN (SELECT id FROM data_series WHERE domain = ?)
                """,
                [cutoff, domain],
            )

        runs_cutoff = (dt.date.today() - dt.timedelta(days=90)).isoformat()
        self.client.query("DELETE FROM data_collection_runs WHERE created_at < ?", [runs_cutoff])
        logs_cutoff = (dt.date.today() - dt.timedelta(days=30)).isoformat()
        exists = _query_rows(self.client.query("SELECT name FROM sqlite_master WHERE type='table' AND name='system_logs'"))
        if exists:
            self.client.query("DELETE FROM system_logs WHERE created_at < ?", [logs_cutoff])
