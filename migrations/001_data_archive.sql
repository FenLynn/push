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
);

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
);

CREATE TABLE IF NOT EXISTS data_collection_runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  domain TEXT NOT NULL,
  collector TEXT NOT NULL,
  status TEXT NOT NULL,
  row_count INTEGER NOT NULL DEFAULT 0,
  detail TEXT,
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_data_series_domain
ON data_series(domain, group_name, location);

CREATE INDEX IF NOT EXISTS idx_data_observations_lookup
ON data_observations(series_id, resolution, observed_on DESC);

CREATE INDEX IF NOT EXISTS idx_data_collection_runs_created
ON data_collection_runs(created_at DESC);
