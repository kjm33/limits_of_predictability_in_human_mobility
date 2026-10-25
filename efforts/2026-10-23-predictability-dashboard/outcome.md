# Outcome — Predictability dashboard (plain language)

## What we did

Built the portfolio Streamlit app over all six datasets: `dashboard/` with `app.py`,
`lib/{config,data,maps}.py`, six pages (Question → Ceiling → Arena → User Explorer →
Suggest → Method), `tests/test_dashboard.py` (15 tests, synthetic data only), a `demo`
uv dependency group (`streamlit`, `plotly`), and a README demo section. Runs via
`uv run --group demo streamlit run dashboard/app.py`.

## What worked

- All acceptance bars verified live: 134 tests green (incl. `st.testing.AppTest` smokes
  for the app + every page), `ruff check src tests scripts dashboard` clean, server
  health "ok" + HTTP 200 on all 6 pages, warm-cache reads 26 ms (bar was < 2 s).
- The dashboard reads only the curated `data/processed/dashboard/` package (~12 MB) —
  no big pipeline file is ever loaded; loaders take overridable base dirs so tests run
  on tmp_path parquets.
- Π framing carried through from the curation review: Π_actual is the headline
  everywhere, Π_unc always labelled "lower bound", entropy-trio ordering shown on the
  ceiling page.
- Suggest page reuses the real `mobility.routines.suggest_destination` + OSRM stack;
  local → public → straight-line fallback never crashes offline; the default
  (geolife user 022 @ Mon 15:14) matches a genuinely mined card, so it triggers
  out of the box.
- Env-var overrides (`MOBILITY_DASHBOARD_DATA`/`_PROCESSED`) let the AppTest smokes
  run the pages against synthetic data.

## What didn't

- `st.scatter_map` no longer exists in streamlit ≥1.6x (upstream removed the maplibre
  element; 1.66 ships pydeck `st.map` again) — spec asked for scatter_map. Solved with
  a `lib/maps.py` compat wrapper that auto-detects; no version pin fight.
- No fsq/gowalla featured user had routine cards, so the Suggest page also offers
  users found in each dataset's `routines.parquet` (gowalla gains 42 options); yjmob
  is excluded with an on-page note (grid data, no cards).
- Streamlit 1.66 logs cosmetic `use_container_width` deprecation warnings (the
  replacement kwarg doesn't exist at our >=1.44 floor). Functional, ignored.

## Bottom line

The 3-effort demo chain is complete: routines/graphs on all datasets → curated
presentation package → interactive dashboard. One command serves a six-page story
("Song said 93%; six datasets and ~350k users later we measure a 0.44–0.65 ceiling,
and the best model flips by regime") with live per-user exploration and the route-
suggestion demo. All work uncommitted in the working tree, ready for review.
