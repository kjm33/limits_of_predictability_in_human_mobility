# Limits of Predictability in Human Mobility — GeoLife + H3

Reproduction of Song et al. (Science, 2010) predictability analysis on the GeoLife
dataset (182 users, Beijing, 2007–2012), plus a pipeline from raw GPS to
**proactive route suggestion** ("every Thursday 15:15 the user drives to music school").

Method background: `notes/2026-10-12-research.md`.
Plain-language results summary: `efforts/2026-10-12-geolife-pipeline/outcome.md`.
Multi-dataset extension (YJMob100K, Foursquare NYC/Tokyo, Gowalla,
Brightkite): `efforts/2026-10-13-multi-dataset-extension/research.md` and
`efforts/2026-10-13-multi-dataset-extension/outcome.md`.

## Demo dashboard

An interactive, six-page Streamlit dashboard tells the whole story — Song 2010's
93% vs the 0.44–0.65 ceiling we actually measure, model leaderboards, per-user
explorer, and a live routine-card → route suggestion demo:

```bash
./run_dashboard.sh
# equivalent to: uv run --group demo streamlit run dashboard/app.py
# extra args pass through, e.g. ./run_dashboard.sh --server.port 8637
```

Pages:

1. **The Question** — hero comparison, plain-words entropy/Fano explainer,
   seven dataset cards, city locator map
2. **Predictability Ceiling** — per-dataset Π_actual distributions/ECDFs,
   Π-vs-q scatter, Fano-bound compliance, entropy trio
3. **Model Arena** — leaderboards, "the winner flips by regime", deep vs best
   baseline, random-walk references, dist-km caveats
4. **User Explorer** — featured users with Π gauge, observed-cell map,
   weekday×hour heatmap, places and POI profiles
5. **Suggest Demo** — the "Monday 15:14" trigger rule with evidence cards and
   an optional OSRM route (degrades to straight-line offline)
6. **Method & Data** — pipeline, provenance, cohort rules, limitations,
   reproduction commands

The dashboard reads only the curated package in `data/processed/dashboard/`
(~12 MB) — never the big pipeline outputs. The `demo` dependency group
(`streamlit`, `plotly`) is optional; everything else runs without it.

## Demo webpage (static scrollytelling)

A lightweight one-page website for a general audience — no equations, no
framework runtime shipped, no browser freeze: hero count-ups, the six datasets,
the noise→places funnel, the H3 hexagon morph (r9→r8), the 15-minute bucket
clock with a live 5/15/60-min resolution comparison, an entropy guessing game,
pattern-detection rates, and an interactive weekday×time trigger that fires a
real routine card for GeoLife user 022.

```bash
make demo-serve    # one command: install deps → build → serve on your LAN (Ctrl+C to stop)
make demo-dev      # or: hot-reload dev server, also LAN-accessible
```

The site's entire data payload (`demo/public/data.json`, ~230 KB) is **committed
to the repo**, so a fresh clone runs the demo with Node.js alone — no Python, no
parquets. Requirements: Node ≥ 20 (`nodejs.org`) and `npm install` (the Makefile
handles both). To regenerate the data after a pipeline change:
`make demo-data` (needs the uv environment and the `data/processed/` tree).

Every number on the page is computed by `scripts/build_demo.py` from
`data/processed/` — nothing hand-typed. Stack: Vite + Svelte 5 + GSAP
ScrollTrigger + MapLibre GL (custom dark style; optional CARTO raster basemap
online, fully functional offline). See
`efforts/2026-11-01-static-demo-website/` and
`reports/2026-11-01-demo-website-analysis.md`.

## Datasets

GeoLife is the primary dataset (above). Five more are integrated through the
same downstream stack (`sequences` → `entropy`/`baselines`/`deep`), each with
its own raw layout and ingest adapter:

| Key | Dataset | Scale | Ingest |
|---|---|---|---|
| `yjmob1` / `yjmob2` | YJMob100K grid (100k/25k users, 500 m grid, 30-min slots) | 180M / 45M hourly cells | `python -m mobility.yjmob` |
| `fsq_nyc` / `fsq_tky` | Foursquare TSMC2014 check-ins | 225k / 573k points | `python -m mobility.checkins` |
| `gowalla` / `brightkite` | SNAP check-ins (+ friendship graphs) | 6.4M / 4.5M points | `python -m mobility.checkins` |

```bash
uv run python scripts/fetch_yjmob100k.py        # or fetch_foursquare / fetch_snap_checkins
uv run python -m mobility.yjmob --dataset yjmob1
uv run python -m mobility.checkins --dataset fsq_nyc
uv run python scripts/run_stage.py entropy --dataset yjmob1   # any stage, any dataset
uv run python scripts/run_stage.py baselines --dataset yjmob1 --shards 8  # 100k-user panels
```

YJMob100K is pre-discretized (no raw GPS), so routing/suggest maps don't
apply there; everything cell-index-based works unchanged.

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
uv run pytest                              # 114 unit tests
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

The sparsity excuse is now closed off: on YJMob100K (100k users, 500 m grid,
q = 0.594 — far denser than GeoLife's 0.905) the Fano Π distribution lands at
mean 0.633 / median 0.639, statistically indistinguishable from GeoLife's
cohort 0.64. Π ≈ 0.63–0.64 appears to be a property of *this class of hourly
next-cell prediction*, not of dataset density. Full cross-dataset tables:
`efforts/2026-10-13-multi-dataset-extension/outcome.md`.

## Repo layout

```
src/mobility/   config, ingest, stay, h3map, sequences, entropy, baselines,
                routines, graphs, deep, yjmob, checkins, routing, suggest
tests/          114 tests (synthetic data; no network except mocked OSRM)
notebooks/      01-06, executed with embedded outputs
reports/        figures (16 png), route maps
efforts/        work history: one dir per effort (spec.md + tasks.md + outcome.md)
STATE.md        where we are now · BACKLOG.md not-yet-done · efforts/README.md index
data/           raw/ + processed/ (flat = GeoLife, per-dataset subdirs)  [gitignored]
```
