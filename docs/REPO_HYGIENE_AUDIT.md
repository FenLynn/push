# Repo Hygiene Audit

Updated: 2026-04-12

## Goal

Keep the repository in a commit-ready state without mixing runtime artifacts, one-off diagnostics, or historical duplicate templates into the tracked codebase.

## Current Decisions

- Deleted garbage files:
  - templates/stock copy.html
  - tmp_audit.py
- Kept as tracked source-of-truth:
  - core/
  - sources/
  - channels/
  - scripts/
  - templates/
  - docs/
  - tests/
- Kept as generated and ignored:
  - logs/
  - output/
  - data/
  - .pytest_cache/

## Audit Summary

### Safe To Remove

- templates/stock copy.html
  - Historical duplicate of the stock template.
  - No production path should depend on a file named as a manual copy.
- tmp_audit.py
  - One-off D1 diagnostic helper.
  - Already ignored by Git and not part of the maintained toolchain.

### Safe To Keep

- scripts/audit_paper_dedup.py
- scripts/audit_paper_doi.py
- scripts/backfill_paper_crossref.py
- scripts/backfill_paper_embedded_metadata.py
- tests/test_paper_dedup.py
  - These are active operational and regression tools added for the paper ingest and dedupe work.

### Generated Runtime Artifacts

- logs/
- output/
- data/
  - These directories are runtime state, not source code.
  - They should remain ignored and can be cleaned operationally without affecting the repo history.

## Documentation Fixes

- README.md previously referenced scripts/cleanup.py, which does not exist.
- The cleanup and retention behavior now correctly points to scripts/fetch_to_d1.py.

## Operational Recommendations

- Before commit, verify only intentional source changes are present with git status.
- Treat output and logs as disposable runtime artifacts.
- Avoid creating hand-copied template variants; use Git history or branches instead.
- Keep new diagnostics in scripts/ only if they are repeatable and operationally useful.