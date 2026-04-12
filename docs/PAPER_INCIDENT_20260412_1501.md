# Paper Incident Audit 2026-04-12 15:01

## Incident Summary

At 2026-04-12 15:01, a manual `paper` push produced a batch that clearly did not match the earlier verification batch.

Observed symptoms:

- Push contained 10 journals and 119 articles.
- The article `Navigating optical skyrmions-from historical origins to applications: tutorial` reappeared.
- The pushed set differed materially from the previous test push and included journals that were not in the earlier batch.

This incident has now been confirmed as a real data integrity problem, not a rendering issue.

## Confirmed Evidence

### 1. The 15:01 push saw a large transient batch

From [output/paper/audit/run_20260412_070127.json](output/paper/audit/run_20260412_070127.json):

- `rawRows = 222`
- `includedArticles = 119`
- `includedJournals = 10`
- `skippedSeen = 58`
- `skippedKeyword = 45`

### 2. The `skyrmions` article was first seen exactly during the 15:00 ingest window

From `paper_push_seen`:

- `source_name = advances in optics and photonics`
- `doi = 10.1364/AOP.569106`
- `first_seen_created_at = 2026-04-12 15:00:44`
- `push_count = 1`

This means it was not an older previously-accounted push item. It entered the push path for the first time during the 15:00-15:01 interval.

### 3. The article is definitely old, not legitimately new

Crossref for `10.1364/AOP.569106` reports:

- journal: `Advances in Optics and Photonics`
- published_at: `2026-03-31`

So by 2026-04-12 15:01, this article was already well outside the intended recent-paper window.

### 4. The 15:01 pushed batch mostly no longer exists in `articles`

Direct D1 verification after the incident showed:

- For `paper_push_seen` rows first recorded between `2026-04-12 15:00:00` and `2026-04-12 15:02:00`:
  - `dedupe_kind = doi`: `93` rows, `93` now missing from `articles`
  - `dedupe_kind = title`: `25` rows, `25` now missing from `articles`

That is `118` first-seen pushed rows from that incident window that are no longer present in the current `articles` table.

### 5. The current `articles` table only retained 2 rows from 15:00-15:02

Current D1 query result for `created_at` between `2026-04-12 15:00:00` and `2026-04-12 15:02:00`:

- only `2` rows remain
- both are `scientific reports`
- the rest of the 15:01 pushed batch is gone

## Conclusion

This incident confirms a generalized version of the earlier `paper`/`rss_fetch` coupling problem:

- `paper` was run while the hourly RSS ingest around 15:00 was still mutating the shared `articles` table.
- `paper` read an unstable intermediate state.
- At least `118` pushed rows from that incident window were transient and are no longer present in `articles`.
- The reappearing `skyrmions` tutorial was one of those transient rows and is objectively an old paper.

So the user judgment was correct: this batch was polluted by RSS activity.

## Scope Of What Is Proven

Proven:

- the 15:01 push batch was contaminated by in-flight RSS ingest state
- the contamination was large, not marginal
- the `skyrmions` article is an old paper and should not have appeared
- the problem is not limited to the fixed 19:00 schedule; any `paper` run overlapping hourly RSS ingest can reproduce it

Not yet fully disambiguated:

- whether each transient row came from `insert-before-cleanup` timing, malformed feed timestamps, or both

That finer distinction requires either:

- per-entry ingest audit logging before cleanup, or
- a stable ingest watermark / batch-finalization mechanism before `paper` reads D1

## Recommended Next Fix Direction

The next repair should target data stability, not UI:

1. `paper` must not read the live mutating `articles` table while hourly RSS ingest is in progress.
2. A stable read boundary is needed, such as an ingest watermark or a finalized batch timestamp.
3. The 19:30 cron stagger remains useful, but it is not sufficient by itself because manual or other near-hour runs can still hit the same class of race.
