# AGENTS.md

Guidance for coding agents working in this repo.

## Environment

- **Always run Python via `uv run <cmd>`** (uv project; `.venv` managed by uv).
- Python 3.14, pandas 3.x, numpy 2.x, h3 4.x, torch CPU-only (custom index in
  `[tool.uv.sources]` — never add CUDA variants).
- 32 cores / 62 GB RAM available; the full pipeline fits in memory.

## Commands

```bash
uv run pytest -q                      # full test suite — MUST pass
uv run ruff check src tests scripts   # line length 100 — MUST pass
uv run python -m mobility.<module>    # run any pipeline stage (see ordering below)
uv run python scripts/run_stage.py <stage> --dataset <key>   # any stage on any dataset
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/XX_*.ipynb
```

Module execution order (each reads predecessors' parquet from `data/processed/`):
`ingest` → `sequences` → `entropy` / `baselines` / `routines` / `graphs` / `deep`
(any order after `sequences`) → `suggest` (CLI demo).

Multi-dataset layout: besides GeoLife (`data/processed/` flat), the processed
tree per dataset lives in `data/processed/<dataset>/` for keys `yjmob1`,
`yjmob2` (via `python -m mobility.yjmob`), `fsq_nyc`, `fsq_tky`, `gowalla`,
`brightkite` (via `python -m mobility.checkins`). Raw files land in
`data/raw/{yjmob100k,foursquare,gowalla,brightkite}/` through
`scripts/fetch_{yjmob100k,foursquare,snap_checkins}.py`. Every stage function
takes `processed_dir=`; `scripts/run_stage.py <stage> --dataset <key>` wires it.

## Hard rules

- **Never write to `data/raw/`**; `data/processed/` is fully regenerable from raw.
- Tests use **synthetic data only** — never read real parquet in unit tests.
  Network is mocked everywhere (OSRM tests mock `requests.get`; caches go to
  `tmp_path`, never the real `data/cache/`).
- Public OSRM demo server is rate-limited 1 req/s and disk-cached — the client
  (`mobility.routing.OsrmClient`) handles throttling; prefer local OSRM
  (`OsrmClient.local()`) when Docker is available.
- Don't commit `data/` (gitignored), secrets, or large binaries.

## pandas 3.x gotchas (bit us before)

- Copy-on-write is default — never mutate a view; use `.copy()` or `to_numpy(copy=True)`.
- No `DataFrame.append` (removed). Use `pd.concat`.
- Timestamps are `datetime64[us]` in memory but **`ms` after a parquet round-trip** —
  never assume ns; compute durations via `.astype("datetime64[s]").astype("int64")`,
  not raw `.astype("int64") // 10**9`.
- GeoLife PLT rows have **7 fields** (`lat,lon,<0>,alt_ft,days,date,time`); parse
  with `usecols=[0,1,3,5,6]`.

## Project conventions

- H3 resolutions: stops at r9; r8/r7/r6 **must** be derived via
  `h3.cell_to_parent(h3_r9)` — point-derived parents mismatch ~7% of cells
  (H3 doesn't nest perfectly).
- Unknown cells are `config.UNKNOWN = -1`; drop them from entropy/history
  contexts, never treat as a real class.
- Splits are per-user chronological (`test_frac=0.2`); Markov contexts may span
  the train/test boundary.
- Result parquets keep the shared column scheme
  `predictor/model, user, n_eval, top1, top3, dist_km` so baselines/deep/graphs
  comparisons stack.
- Ruff rules include B (bugbear): `zip(..., strict=True)`, no mutable defaults.
- Notebooks resolve the project root by walking up from `notebooks/` cwd —
  don't assume `os.getcwd()` is the repo root inside them.
- **Ignore pyright "import could not be resolved" diagnostics** — stale venv
  noise present on every file; the env itself is verified working.

## Module map (src/mobility/)

| Module | Responsibility |
|---|---|
| `config` | paths + constants (stay params, H3 res, cohort thresholds, dataset dirs) |
| `ingest` / `stay` / `h3map` | PLT parse → points → stays/trips (250 m / 10 min, 20-min merge gap) |
| `sequences` / `entropy` | hourly most-frequent-cell sequences; S_rand/S_unc/S_LZ + Fano Π |
| `baselines` | freq / time-conditioned / Markov (order 1-3, individual+collective) predictors + metrics |
| `routines` | DBSCAN places, routine cards (weekday × 15-min bucket), trigger rule |
| `graphs` | per-user/global transition graphs, analytics, random-walk predictor |
| `deep` | DeepMove-style RNN, causal Transformer, GraphSeq (PPR embeddings) — torch CPU |
| `yjmob` | YJMob100K grid adapter: writes seq_hourly/cells_r8/seq_q/cohort/poi directly (no raw GPS) |
| `checkins` | Foursquare TSMC2014 + Gowalla/Brightkite check-in parse → points/checkins_meta |
| `routing` / `suggest` | OSRM client + folium maps; `python -m mobility.suggest` CLI |

## Definition of done

Any change: `uv run pytest -q` green + `uv run ruff check src tests scripts` clean.
If a pipeline module changed, re-run it against real data and refresh affected
notebook outputs + `reports/` figures.
