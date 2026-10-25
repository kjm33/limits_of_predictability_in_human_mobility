# Predictability dashboard

Status: done   <!-- draft | active | done | abandoned — update when it changes -->
Start: 2026-10-23
End: 2026-10-23

## Goal

A portfolio-grade Streamlit dashboard that presents all six datasets' predictability
results as an interactive story ("how predictable is human movement, and where's the
ceiling?").

## Expected results

- `dashboard/` with `app.py` (entry + nav), `lib/config.py` (dataset registry:
  key → label, city, color, dir, has_coords, q, cohort), `lib/data.py` (cached loaders +
  aggregation helpers, unit-testable)
- 6 pages: 1_The_Question (hero: Song 2010's 0.93 vs our 0.63, dataset cards, city
  locator), 2_Predictability_Ceiling (Π distributions, Π-vs-q scatter, Fano-bound
  compliance, entropy trio), 3_Model_Arena (leaderboards, "winner flips by regime",
  deep vs best baseline, random walk), 4_User_Explorer (per-user Π gauge, cell map,
  activity heatmap, top venues/POI), 5_Suggest_Demo (live routine card → destination →
  OSRM route map, straight-line fallback offline), 6_Method_Data (limitations, cohort
  thresholds, repro commands)
- New `demo` dependency group (`streamlit`, `plotly`); run via
  `uv run --group demo streamlit run dashboard/app.py`
- Maps via built-in `st.scatter_map` (folium fallback only if it underperforms)
- Dashboard reads only result parquets + curated `data/processed/dashboard/` package;
  big files (`points`, yjmob1 `seq_hourly`) never loaded whole
- `tests/test_dashboard.py` (synthetic data); README demo section

## Non-goals

- No new analysis or models — presentation over existing + curated results only
- No hosting/deployment, no auth
- No changes to pipeline stages

## Acceptance criteria

- [x] `uv run --group demo streamlit run dashboard/app.py` serves all 6 pages
- [x] Warm-cache page loads < ~2 s (26 ms re-reads, AppTest-verified)
- [x] `uv run pytest -q` green; `uv run ruff check` extended to and clean on `dashboard/`
- [x] README has a demo section with the run command

## References

- Depends on: 2026-10-23-demo-curation (curated parquet package)
- Existing suggest demo: `python -m mobility.suggest` (src/mobility/suggest.py)
- OSRM note: local (`OsrmClient.local()`) preferred, public demo rate-limited 1 req/s
