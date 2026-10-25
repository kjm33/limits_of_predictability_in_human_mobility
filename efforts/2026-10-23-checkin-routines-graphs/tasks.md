# Tasks — Check-in routines + graphs

**Status: DONE 2026-10-23** — all tasks complete; see outcome.md. Deferred: friendship-edge
wiring + check-in card thresholds → BACKLOG.md.

## Plan

1. Verify stage compatibility: `routines.py`/`graphs.py` read stops/places via
   `processed_dir=`; check column expectations against check-in `stops` output. Check
   venue-name availability for card labels; check friendship-edge wiring in `graphs.py`.
2. Run stages per dataset (`routines` ×4, `graphs` ×4) via `scripts/run_stage.py`.
3. Validate outputs vs GeoLife schemas; sanity-check place/card counts per dataset.
4. If cards are coords-only: minimal venue enrichment (join nearest check-in venue
   names) + unit tests.
5. Acceptance commands; close out.

## Tasks

- [x] 2026-10-23: verify routines/graphs stage inputs on check-in processed dirs
      (stages are dataset-agnostic; fsq_nyc routines smoke-run OK — 706 places / 11 cards
      at GeoLife thresholds; SNAP checkins_meta has loc_id only, no venue cats)
- [x] code: graphs.py — groupby-based evaluate_random_walk + seq cohort filter + tests
- [x] code: routines.py — attach_venue_context enrichment + tests
- [x] run routines on fsq_nyc (706 places/11 cards), fsq_tky (2,101/77), gowalla
      (22,040/72), brightkite (17,409/914) + GeoLife refresh (640/244)
- [x] run graphs on fsq_nyc (62 users), fsq_tky (494), gowalla (1,954), brightkite
      (2,757) + GeoLife refresh (76; old rw_results had seq-only garbage rows — cleaned)
- [x] verify venue names in places_summary: fsq_nyc top cats Bar/Office/Coffee Shop,
      fsq_tky Train Station/Subway/Electronics; SNAP zeroed (uniform 10-col schema)
- [x] friendship edges: confirmed NOT wired into graphs stage — gap documented in
      outcome.md, item already in BACKLOG.md
- [x] acceptance: `uv run pytest -q` green (119) + ruff clean; schemas uniform across
      5 dirs; notebooks 04/05 re-executed

## Blockers / open questions

- none yet
