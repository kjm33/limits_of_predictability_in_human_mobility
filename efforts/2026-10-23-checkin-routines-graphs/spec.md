# Check-in routines + graphs

Status: done   <!-- draft | active | done | abandoned — update when it changes -->
Start: 2026-10-23
End: 2026-10-23   <!-- set at close-out -->

## Goal

Routine mining and transition-graph analytics exist for the four check-in datasets
(fsq_nyc, fsq_tky, gowalla, brightkite), not just GeoLife — giving the planned dashboard
multi-city routine cards with venue context and a random-walk predictor in the model
comparison.

## Expected results

- `data/processed/{fsq_nyc,fsq_tky,gowalla,brightkite}/` contain `places`,
  `places_summary`, `routines`, `trigger_eval` (routines stage) and `graphs/*.graphml`,
  `graph_analytics`, `rw_results` (graphs stage)
- Routine cards reference venue names from `checkins_meta` where a place maps to check-in
  venues — or, if the current code is coords-only, a minimal card-enrichment task is added
  and tested
- Friendship edges (gowalla/brightkite) verified as wired into `graphs.py` or the gap
  documented in outcome.md

## Non-goals

- No yjmob routines/graphs (grid data, no coordinates for DBSCAN)
- No deep-model runs (yjmob1 deep stays in BACKLOG)
- No new predictors, no stage-interface changes

## Acceptance criteria

- [x] `uv run python scripts/run_stage.py routines --dataset fsq_nyc` (and fsq_tky,
      gowalla, brightkite) exits 0
- [x] `uv run python scripts/run_stage.py graphs --dataset fsq_nyc` (and fsq_tky,
      gowalla, brightkite) exits 0
- [x] Output parquet schemas match GeoLife counterparts (shared column scheme)
- [x] `uv run pytest -q` green (119); `uv run ruff check src tests scripts` clean

## References

- efforts/2026-10-13-multi-dataset-extension/ (wired the check-in ingest)
- notes/2026-10-13-research-datasets.md, notes/2026-10-14-new-datasets-results.md
- Downstream: 2026-10-23-demo-curation → 2026-10-23-predictability-dashboard
