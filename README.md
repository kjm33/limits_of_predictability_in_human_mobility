# Limits of Predictability in Human Mobility — GeoLife + H3

Reproduction of Song et al. (Science, 2010) predictability analysis on the GeoLife
dataset (182 users, Beijing, 2007–2012), plus a pipeline from raw GPS to
**proactive route suggestion** ("every Thursday 15:15 the user drives to music school").

Method background: `notes/research-2026-10-12.md`.
Plain-language results summary: `notes/results-plain-2026-10-12.md`.

## Pipeline

| Phase | Module | Output (`data/processed/`) |
|---|---|---|
| 1. Ingestion & stop detection (Zheng 2009: 250 m / 10 min) | `mobility.ingest`, `mobility.stay`, `mobility.h3map` | `points`, `stops`, `trips`, `coverage_stats`, `cohort` |
| 2. Hourly sequences + entropy trio & Fano Π | `mobility.sequences`, `mobility.entropy` | `seq_hourly`, `cells_r8`, `seq_q`, `entropy` |
| 3. Statistical baselines | `mobility.baselines` | `baseline_hourly_results`, `baseline_trip_results` |
| 4. Routine mining + trigger rule | `mobility.routines` | `places`, `places_summary`, `routines`, `trigger_eval` |
| 5. Transition graphs + random walk | `mobility.graphs` | `graphs/*.graphml`, `graph_analytics`, `rw_results` |
| 6. Deep learning (torch CPU) | `mobility.deep` | `deep_results` (+ `data/cache/deep/*.pt`) |
| 7. Route suggestion | `mobility.routing`, `mobility.suggest` | `reports/suggest_<user>.html` |

Each module is runnable directly, in order:

```bash
uv sync                                    # core deps (+ pytest/ruff/jupyter dev group)
uv run python scripts/fetch_geolife.py     # download + extract GeoLife (~1.5 GB zip)
uv run python -m mobility.ingest           # PLT -> points/stops/trips/cohort (~1 min)
for m in sequences entropy baselines routines graphs deep; do
  uv run python -m mobility.$m
done
uv run pytest                              # 93 unit tests
uv run ruff check src tests
```

Notebooks 01–06 (executed, figures in `reports/`) cover each phase:
QC → entropy/Π → baselines → routines → graphs → deep models.

## Demo — proactive route suggestion

```bash
uv run python -m mobility.suggest --user 022 --now "Mon 15:14" --route
```

```
user 022 @ Mon 15:14 from (39.9687, 116.3470)

#1 -> (39.9704, 116.3034)  score 1.00
    seen 3x over 3 weeks (15:00-15:15, conf 1.00, stab 1.00, last 2009-06-29)

route (osrm): 5.5 km, 7 min -> reports/suggest_022.html
```

`--now` accepts weekday+time (resolved to the next such day) or an ISO datetime;
`--at 'lat,lon'`/`--at work` overrides the origin (default: home place). Routing
uses a local OSRM (`http://localhost:5000`) if reachable, else the public OSRM
demo server (1 req/s, disk-cached), else a straight-line fallback. To run OSRM
locally:

```bash
docker run -d --name osrm -p 5000:5000 osrm/osrm-backend osrm-routed \
  --algorithm mld /data/beijing-latest.osrm  # after preparing an extract
```

## Headline results

| Quantity | Value | Paper (Song 2010) |
|---|---|---|
| Cohort | 76 / 182 users (≥30 active days, ≥5 distinct r8 cells) | 45k phone users |
| Π_actual (Fano) mean | 0.55 all users / 0.64 cohort | 0.93 |
| Best hourly baseline (markov3_col) | top-1 0.231, top-3 0.393 | — |
| Transformer (torch, CPU) | top-1 0.260, top-3 0.416 | — |
| Fano bound respected per-user | 95.6% of users | 93% (paper's Π headline) |
| Routine trigger precision / recall | 0.90 / 0.75 (micro) | — |

Our Π is far below the paper's 93%: GeoLife's whole-enrollment hourly grid is
much sparser (mean q ≈ 0.84) than the paper's dense call-inferred locations —
notebook 02 quantifies this honestly rather than chasing the headline.

## Repo layout

```
src/mobility/   config, ingest, stay, h3map, sequences, entropy, baselines,
                routines, graphs, deep, routing, suggest
tests/          93 tests (synthetic data; no network except mocked OSRM)
notebooks/      01-06, executed with embedded outputs
reports/        figures (16 png), route maps, research notes
data/           raw/ (GeoLife) + processed/ (parquet artifacts)  [gitignored]
```
