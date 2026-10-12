# Plan: Predictive Route Suggestion from Mobility Patterns (GeoLife + H3)

Created: 2026-10-12
Dataset: GeoLife (Microsoft) — 182 users, Beijing, 2007–2012, 1–5 s GPS
Stack: Python 3.12 (uv), h3, pandas/pyarrow, networkx, scikit-learn, PyTorch, OSRM (docker)
Research note: `notes/research-2026-10-12.md`

## Phase 0 — Project setup
- [ ] 0.1 Init uv project (`pyproject.toml`), `src/mobility/` package layout, `.gitignore`, `README.md`
- [ ] 0.2 Add deps: pandas, numpy, pyarrow, h3, scikit-learn, networkx, tqdm, matplotlib, folium, requests, jupyter, pytest; torch (CPU) later in Phase 6
- [ ] 0.3 Download GeoLife zip (~1.5 GB, https://www.microsoft.com/en-us/download/details.aspx?id=52367) → `data/raw/` → extract → verify 182 users / 17,621 plt files

## Phase 1 — Ingestion & stop detection on H3
- [ ] 1.1 PLT parser + labels.txt transport modes → consolidated Parquet (`data/processed/points.parquet`), QC (jitter drop, trajectory segmentation on gaps)
- [ ] 1.2 Stay-point detection (Zheng 2009 params: ~250 m / ≥10 min) → stops timeline `(user, h3_r8, arrive, depart, dwell)` + trips (origin→dest)
- [ ] 1.3 Multi-resolution H3 mapping (r9 stops detail, r8 primary, r6/7 corridors); per-user coverage stats; select modeling cohort (enough active days)
- [ ] 1.4 Unit tests: parser, H3 mapping, stay detection on synthetic traces

## Phase 2 — Predictability analysis (Song et al. 2010 reproduction)
- [ ] 2.1 Hourly-binned cell sequences per user; unknown-interval fraction q per user
- [ ] 2.2 Entropy trio: S_rand, S_unc, actual entropy (Lempel-Ziv/Kontoyiannis estimator) — unit test on synthetic sequences with known entropy
- [ ] 2.3 Fano → per-user Π distribution; figures vs paper's ~93%; notebook `02_predictability.ipynb`

## Phase 3 — Statistical baselines
- [ ] 3.1 Time-conditioned frequency predictor (hour-of-week × cell)
- [ ] 3.2 Order-k Markov chains (k=1,2,3) over H3 r8, individual vs collective, backoff smoothing
- [ ] 3.3 Temporal split (80/20); metrics: top-1/top-3 accuracy, centroid distance error (km), trip-destination accuracy; notebook `03_baselines.ipynb`

## Phase 4 — Routine mining (Thursday-15:15 detector)
- [ ] 4.1 Day-of-week × 15-min-bucket origin→destination profiles per user
- [ ] 4.2 Periodic pattern miner: `(origin cluster, dest cluster, weekday, time window, support, confidence, stability)` → routine cards
- [ ] 4.3 Trigger rule P(dest | now, recent cells) ≥ threshold; precision/recall eval of suggestions; notebook `04_routines.ipynb` + routine heatmap & mobility-graph figures

## Phase 5 — Graph modeling
- [ ] 5.1 Per-user directed weighted H3 transition graphs (networkx; node dwell stats, edge counts + time-of-day histograms); export graphml
- [ ] 5.2 Graph analytics: home/work inference (dwell × hour-of-week), communities, centrality; global cross-user transition graph as spatial prior
- [ ] 5.3 Random-walk next-cell predictor; compare vs Phase 3; notebook `05_graphs.ipynb`

## Phase 6 — Deep learning
- [ ] 6.1 Add torch (CPU); dataset/dataloader over (cell idx, time features) sequences
- [ ] 6.2 DeepMove-style attention-RNN; small from-scratch Transformer
- [ ] 6.3 GNN head (GCN/GAT over H3 transition graph) — MobGT-lite; notebook `06_deep.ipynb`; fair comparison vs Phases 3 & 5

## Phase 7 — Route suggestion demo
- [ ] 7.1 Local OSRM docker on Beijing OSM extract (fallback: OSRM demo server with caching)
- [ ] 7.2 Destination→route module (centroid snap, route fetch, folium map)
- [ ] 7.3 Demo: simulate "Thu 15:15" for a user with a strong routine → predicted dest + route + routine evidence; CLI `python -m mobility.suggest --user X --now "Thu 15:15"`
- [ ] 7.4 Final README: end-to-end reproduction instructions

## Verification & conventions
- Every phase: notebook artifact + committed figures in `reports/`
- `pytest` green before phase completion; ruff format/lint
- .opencode LSP: pyright configured (`.opencode/opencode.json`)
