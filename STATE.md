# State — where we are now (2026-10-23)

> One screen. Read this at session start. Update at session end (30-second anti-drift rule).

## Active efforts

| Effort | Since | State | Next |
|---|---|---|---|
| none — both efforts closed out | | | pick from `BACKLOG.md` |

## Live numbers

- Tests: 114 green (`uv run pytest -q`); lint clean (`uv run ruff check src tests scripts`)
- GeoLife cohort: 76/182 users; Π mean 0.55 all / 0.64 cohort (paper: 0.93); Fano bound respected by 95.6% of users
- Best hourly baseline `markov3_col` top-1 0.231 / top-3 0.393; Transformer 0.260 / 0.416
- Routine trigger precision/recall 0.90 / 0.75 (micro)
- Cross-dataset: YJMob100K Π mean 0.633 (q = 0.594, far denser than GeoLife) — Π tracks the
  sensing regime, not density (details: `efforts/2026-10-13-multi-dataset-extension/outcome.md`)
- Datasets processed under `data/processed/`: GeoLife (flat) + `yjmob1`, `yjmob2`, `fsq_nyc`,
  `fsq_tky`, `gowalla`, `brightkite`

## Blocked

- none known

## Next

1. Pick from `BACKLOG.md` (yjmob1 deep run, Brightkite unfiltered rerun, friendship graphs,
   disruption analysis, DeepMove benchmark)
2. New work >~½ day / multi-file / interface-touching → follow the `sdd` skill
   (effort dir from `efforts/_TEMPLATE/`, spec review before implementation)
