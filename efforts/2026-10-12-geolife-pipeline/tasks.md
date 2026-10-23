# Tasks — GeoLife pipeline (predictive route suggestion from mobility patterns)

Status: done (2026-10-12 → 2026-10-12)

> Retrofitted into SDD 2026-10-23 (was `plans/plan.md`). The plan was never checked off as
> work landed; boxes below are ticked from commit evidence 259e283…8d0abb4, docs commits
> 6aa4d32…8d0abb4, and `outcome.md`.

Dataset: GeoLife (Microsoft) — 182 users, Beijing, 2007–2012, 1–5 s GPS
Stack: Python 3.12 (uv), h3, pandas/pyarrow, networkx, scikit-learn, PyTorch, OSRM (docker)
Research note: `../../notes/2026-10-12-research.md`

## Phase 0 — Project setup
- [x] 2026-10-12: 0.1 Init uv project (`pyproject.toml`), `src/mobility/` package layout, `.gitignore`, `README.md`
- [x] 2026-10-12: 0.2 Add deps: pandas, numpy, pyarrow, h3, scikit-learn, networkx, tqdm, matplotlib, folium, requests, jupyter, pytest; torch (CPU) later in Phase 6
- [x] 2026-10-12: 0.3 Download GeoLife zip (~1.5 GB) → `data/raw/` → extract → verify 182 users / 17,621 plt files

## Phase 1 — Ingestion & stop detection on H3
- [x] 2026-10-12: 1.1 PLT parser + labels.txt transport modes → consolidated Parquet (`data/processed/points.parquet`), QC (jitter drop, trajectory segmentation on gaps)
- [x] 2026-10-12: 1.2 Stay-point detection (Zheng 2009 params: ~250 m / ≥10 min) → stops timeline `(user, h3_r8, arrive, depart, dwell)` + trips (origin→dest)
- [x] 2026-10-12: 1.3 Multi-resolution H3 mapping (r9 stops detail, r8 primary, r6/7 corridors); per-user coverage stats; select modeling cohort (enough active days)
- [x] 2026-10-12: 1.4 Unit tests: parser, H3 mapping, stay detection on synthetic traces

## Phase 2 — Predictability analysis (Song et al. 2010 reproduction)
- [x] 2026-10-12: 2.1 Hourly-binned cell sequences per user; unknown-interval fraction q per user
- [x] 2026-10-12: 2.2 Entropy trio: S_rand, S_unc, actual entropy (Lempel-Ziv/Kontoyiannis estimator) — unit test on synthetic sequences with known entropy
- [x] 2026-10-12: 2.3 Fano → per-user Π distribution; figures vs paper's ~93%; notebook `02_entropy_predictability.ipynb`

## Phase 3 — Statistical baselines
- [x] 2026-10-12: 3.1 Time-conditioned frequency predictor (hour-of-week × cell)
- [x] 2026-10-12: 3.2 Order-k Markov chains (k=1,2,3) over H3 r8, individual vs collective, backoff smoothing
- [x] 2026-10-12: 3.3 Temporal split (80/20); metrics: top-1/top-3 accuracy, centroid distance error (km), trip-destination accuracy; notebook `03_baselines.ipynb`

## Phase 4 — Routine mining (Thursday-15:15 detector)
- [x] 2026-10-12: 4.1 Day-of-week × 15-min-bucket origin→destination profiles per user
- [x] 2026-10-12: 4.2 Periodic pattern miner: `(origin cluster, dest cluster, weekday, time window, support, confidence, stability)` → routine cards
- [x] 2026-10-12: 4.3 Trigger rule P(dest | now, recent cells) ≥ threshold; precision/recall eval of suggestions; notebook `04_routines.ipynb` + routine heatmap & mobility-graph figures

## Phase 5 — Graph modeling
- [x] 2026-10-12: 5.1 Per-user directed weighted H3 transition graphs (networkx; node dwell stats, edge counts + time-of-day histograms); export graphml
- [x] 2026-10-12: 5.2 Graph analytics: home/work inference (dwell × hour-of-week), communities, centrality; global cross-user transition graph as spatial prior
- [x] 2026-10-12: 5.3 Random-walk next-cell predictor; compare vs Phase 3; notebook `05_graphs.ipynb`

## Phase 6 — Deep learning
- [x] 2026-10-12: 6.1 Add torch (CPU); dataset/dataloader over (cell idx, time features) sequences
- [x] 2026-10-12: 6.2 DeepMove-style attention-RNN; small from-scratch Transformer
- [x] 2026-10-12: 6.3 GNN head *(delivered as GraphSeq: frozen PPR embeddings + linear head, not GCN/GAT — see outcome.md)*; notebook `06_deep_learning.ipynb`; fair comparison vs Phases 3 & 5

## Phase 7 — Route suggestion demo
- [x] 2026-10-12: 7.1 OSRM routing *(demo server with disk-cache + straight-line fallback; local docker optional)*
- [x] 2026-10-12: 7.2 Destination→route module (centroid snap, route fetch, folium map)
- [x] 2026-10-12: 7.3 Demo: simulate "Thu 15:15" for a user with a strong routine → predicted dest + route + routine evidence; CLI `python -m mobility.suggest --user X --now "Thu 15:15"`
- [x] 2026-10-12: 7.4 Final README: end-to-end reproduction instructions

## Verification & conventions
- [x] Every phase: notebook artifact + committed figures in `reports/`
- [x] `pytest` green before phase completion (114 tests); ruff format/lint
- [x] .opencode LSP: pyright configured (`.opencode/opencode.json`)
