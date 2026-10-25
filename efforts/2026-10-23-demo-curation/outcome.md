# Outcome — Demo curation (plain language)

## What we did

We decided — in code, reproducibly — what the dashboard is allowed to show. A new notebook
(07_demo_curation.ipynb, executed) reads all seven datasets' result parquets and writes a
small "curated package" (`data/processed/dashboard/`, 53 parquets, ~12 MB): one headline
row per dataset, the full user-level Π table, a model leaderboard (baselines + random walk
+ deep), 15 editorially-chosen featured users, and per-user extracts (hourly sequence with
coordinates, routine cards, places, yjmob POI profile) so the dashboard never touches the
big panels — worst-case featured-user load is 8 ms.

## What worked

- **The Π story survived contact with curation.** Headline table: Π_actual ≈ 0.44–0.65
  across sensing regimes (geolife 0.553 all / 0.637 cohort, yjmob1 0.633, brightkite 0.654,
  gowalla 0.437) vs Song 2010's 0.93 — same numbers as the published notes, now in one
  reloadable parquet.
- **Featured users span the spectrum**: 0.02 (gowalla wanderer) to 0.997 (brightkite
  homestayer) Π_actual, including GeoLife 022 (routing flagship, Π 0.864 — also geolife's
  most predictable user, a nice coincidence for the demo) and brightkite 9957 (39 routine
  cards, honest NaN Π — one-cell history).
- yjmob1's 180M-row panel extracts per-user in 0.1 s via pyarrow pushdown — the size
  mountain turned into a molehill.

## What didn't

- **A headline-column mixup was caught in review** (worth remembering): the first pass
  promoted Π_unc — the *frequency-only* ceiling — as "the ceiling", producing 0.36–0.46
  "Π" values that contradicted every published note. The Song-comparable number is
  Π_actual (actual/LZ entropy → Fano, the same inversion Song used); Π_unc is now context,
  and the Fano-compliance fraction was also inverted (fixed: geolife 0.934, yjmob 1.000).
  The notebook now explains the trio Π_rand ≤ Π_unc ≤ Π_actual explicitly.
- `routine_creature` brightkite 9957 has NaN Π (single distinct cell — the Fano inversion
  is undefined at N=1). Kept, surfaced honestly, explained in the note.

## Bottom line

Effort 3 (the Streamlit dashboard) is now a pure presentation job: every number it needs
lives in `data/processed/dashboard/` with documented schemas
(notes/2026-10-23-demo-curation.md), including per-user data for the explorer page.
