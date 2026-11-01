# State — where we are now (2026-11-01)

> One screen. Read this at session start. Update at session end (30-second anti-drift rule).

## Active efforts

| Effort | Since | State | Next |
|---|---|---|---|
| (none — demo webpage closed 2026-11-01) | | | pick next from `BACKLOG.md` |

## Live numbers

- Tests: 143 green (`uv run pytest -q`); lint clean (`uv run ruff check src tests scripts dashboard`)
- **Demo webpage (static scrollytelling)**: `make demo-serve` (builds + serves
  on LAN, port 4173) or `make demo-dev`; data.json (250 KB) is committed, so a
  fresh clone needs only Node ≥ 20 — regenerate with `make demo-data`;
  9 scenes. No map library anymore (MapLibre + HERE basemap removed at user
  request): the hexagon explainer is a schematic SVG (7 r9 cells → 1 r8 parent
  → r7 district) and the trigger scene is a single-column weekday×time
  console. See README "Demo webpage"
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
