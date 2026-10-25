# Demo curation

Status: done   <!-- draft | active | done | abandoned — update when it changes -->
Start: 2026-10-23
End: 2026-10-23   <!-- set at close-out -->

## Goal

A documented, reproducible selection of *what the dashboard presents* — headline numbers,
featured users, curated aggregates — so the dashboard build (next effort) is
presentation-only.

## Expected results

- `notebooks/07_demo_curation.ipynb`, executed: per-dataset headline table, featured-user
  picks (high/low Π exemplars, dense histories, interesting routines) with rationale, and
  curated parquets written to `data/processed/dashboard/` (e.g. `dataset_summary`,
  `featured_users`, `leaderboards`, `pi_distributions`)
- `notes/2026-10-23-demo-curation.md`: the "what we present and why" report incl. curated
  schema docs

## Non-goals

- No dashboard code
- No pipeline/stage changes
- Figures live inside the notebook only (no new `reports/` pngs)

## Acceptance criteria

- [x] `uv run jupyter nbconvert --to notebook --execute --inplace notebooks/07_demo_curation.ipynb` exits 0
- [x] Curated parquets exist under `data/processed/dashboard/`; schemas documented in the note
- [x] Featured users verified loadable per dataset (worst case 8 ms; pyarrow pushdown)
- [x] `uv run pytest -q` green (119); `uv run ruff check src tests scripts` clean

## References

- Depends on: 2026-10-23-checkin-routines-graphs (routine/graph outputs for check-ins)
- Feeds: 2026-10-23-predictability-dashboard
- Source numbers: notes/2026-10-14-new-datasets-results.md
