# State — where we are now (2026-11-01)

> One screen. Read this at session start. Update at session end (30-second anti-drift rule).

## Active efforts

| Effort | Since | State | Next |
|---|---|---|---|
| (none — demo webpage closed 2026-11-01) | | | pick next from `BACKLOG.md` |

## Live numbers

- Tests: 143 green (`uv run pytest -q`); lint clean (`uv run ruff check src tests scripts dashboard`)
- **Demo webpage (static scrollytelling)**: rebuild data with
  `uv run python scripts/build_demo.py` (→ 232 KB `demo/public/data.json`),
  view with `cd demo && npm run dev` — 9 scenes, first load ~420 KB wire,
  MapLibre lazy; see README "Demo webpage (static scrollytelling)"
- **Demo dashboard**: `uv run --group demo streamlit run dashboard/app.py` — six pages
  over the curated package in `data/processed/dashboard/` (~12 MB, 26 ms warm reads);
  see README "Demo dashboard"
- GeoLife cohort: 76/182 users; Π mean 0.55 all / 0.64 cohort (paper: 0.93); Fano bound respected by 95.6% of users
- Best hourly baseline `markov3_col` top-1 0.231 / top-3 0.393; Transformer 0.260 / 0.416
- Routine trigger precision/recall 0.90 / 0.75 (micro); on check-ins 97%+ trigger hit rate
  (brightkite 683/692, gowalla 62/64); % users with routine cards: geolife 44.7%,
  brightkite 12.0%, gowalla 2.0%
- Cross-dataset: YJMob100K Π mean 0.633 (q = 0.594, far denser than GeoLife) — Π tracks the
  sensing regime, not density (details: `efforts/2026-10-13-multi-dataset-extension/outcome.md`)
- routines+graphs now run on ALL datasets (shared schema; RW hourly top-1: geolife 0.191,
  fsq_nyc 0.148, fsq_tky 0.140, brightkite 0.156, gowalla 0.058); fsq places carry venue
  categories (NYC: Bar/Office/Coffee Shop; TKY: Train Station/Subway/Electronics)
- Datasets processed under `data/processed/`: GeoLife (flat) + `yjmob1`, `yjmob2`, `fsq_nyc`,
  `fsq_tky`, `gowalla`, `brightkite`

## Blocked

- none known

## Next

1. Demo chain complete (checkin-routines-graphs + demo-curation + predictability
   dashboard, closed 2026-10-23; static demo webpage closed 2026-11-01)
2. Pick from `BACKLOG.md` (yjmob1 deep run, Brightkite unfiltered rerun,
    disruption analysis, DeepMove benchmark, friendship graphs)
    (effort dir from `efforts/_TEMPLATE/`, spec review before implementation)
