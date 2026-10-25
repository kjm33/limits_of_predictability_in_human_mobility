# Efforts index

What has been done. Current state: `../STATE.md`. Not yet done: `../BACKLOG.md`.
Per-effort dirs: `YYYY-MM-DD-<slug>/` (spec.md + tasks.md + outcome.md). Template: `_TEMPLATE/`.

| Started | Effort | Status | Outcome (one line) |
|---|---|---|---|
| 2026-10-12 | [GeoLife pipeline](2026-10-12-geolife-pipeline/) | done | Song-2010 reproduction on GeoLife (Π 0.64 cohort vs paper's 0.93 — sparsity honestly explained) + full GPS→route-suggestion pipeline, 7 phases, 114 tests |
| 2026-10-13 | [Multi-dataset extension](2026-10-13-multi-dataset-extension/) | done | YJMob100K + Foursquare + Gowalla/Brightkite wired into one stack; Π ≈ 0.63–0.64 across sensing regimes — density is not the limit |
| 2026-10-23 | [Check-in routines + graphs](2026-10-23-checkin-routines-graphs/) | done | routines+graphs on all 4 check-in datasets, one shared schema; venue enrichment (NYC=Bars, Tokyo=Stations); RW evaluator made 231M-row-scalable; trigger rule holds on check-ins (97%+ hit) |
| 2026-10-23 | [Demo curation](2026-10-23-demo-curation/) | done | curated dashboard package (headline Π_actual table, leaderboards, 15 featured users, 8 ms per-user loads); review caught Π_unc-as-headline mixup |
| 2026-10-23 | [Predictability dashboard](2026-10-23-predictability-dashboard/) | done | six-page Streamlit story over the curated package (0.93-vs-0.44–0.65 hero, arena, user explorer, live suggest demo); 134 tests, 26 ms warm reads |
