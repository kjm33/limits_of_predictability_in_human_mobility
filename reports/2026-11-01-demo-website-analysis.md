# Static demo website — analysis and plan

2026-11-01 · Why the Streamlit demo feels heavy/enigmatic, what the demo must show (verified numbers), and the agreed Tier-2 web stack

## Question

The user reports: the current demo is ugly, heavy (browser freezes), and speaks
math-jargon (entropy equations). After adding datasets beyond GeoLife the results
became "enigmatic". Goal: an impressive, easy-to-understand web demo that presents
(1) the collected data/datasets, (2) statistics — how many users, how long,
(3) in what % of users we detect patterns and how confident those patterns are —
plus strong explainer scenes for preprocessing (Uber's H3 hexagons, 15-minute
buckets) and the weekday/time trigger.

## Method

Session analysis (2026-11-01) of both checkouts — the `analyze_w_astra` worktree
(frozen at c91579f, no data) and this master repo (demo chain closed 2026-10-23) —
plus direct queries against `data/processed/` parquets (`dataset_summary`,
`routines.parquet` × 5 datasets, `points.parquet` spans/counts, curated user-022
extracts).

## Results

### Current state

- This repo already has a six-page Streamlit dashboard over a curated 12 MB package
  (`data/processed/dashboard/`), 134 tests green — but it frames the *science* story
  (Π ceiling vs Song 2010), loads parquet/Plotly per page (the freeze), and uses
  technical language.
- The "enigma" after adding datasets is a finding, not a failure: both the
  predictability ceiling and the winning model track the **sensing regime** (how
  people were watched), not the people.

### Dataset table (verified 2026-11-01)

| Dataset | People | Records | How long | How watched |
|---|---|---|---|---|
| GeoLife (Beijing) | 182 | 24.8M GPS points | 2007–2012, median cohort user seen on 75 days | GPS logger 1–5 s |
| YJMob100K ds1/ds2 (Japan) | 100,000 / 25,000 | 111.5M grid pings | 75 days each | app pings, 500 m grid |
| Foursquare NYC / Tokyo | 1,083 / 2,293 | 0.2M / 0.6M check-ins | ~10 months | voluntary check-ins |
| Gowalla (global) | 107,069 | 6.4M check-ins | ~20 months | voluntary check-ins |
| Brightkite (global) | 50,686 raw / 8,173 kept | 4.5M check-ins | ~2.5 years | voluntary check-ins |

### Pattern detection (routines.parquet per dataset; cohort = users with enough data)

| Dataset | Users w/ routines | Share | Cards | Mean confidence | Median confidence |
|---|---|---|---|---|---|
| GeoLife | 34 of 76 | **44.7%** | 244 | 0.93 | 1.00 |
| Brightkite | 330 of 2,757 | **12.0%** | 914 | 0.996 | 1.00 |
| Foursquare NYC | 6 of 62 | 9.7% | 11 | 0.94 | 1.00 |
| Foursquare Tokyo | 38 of 494 | 7.7% | 77 | 0.98 | 1.00 |
| Gowalla | 40 of 1,954 | 2.0% | 72 | 0.99 | 1.00 |
| YJMob100K | n/a — grid data, no place detection | — | 0 | — | — |

Rule guarantees: every card held in ≥3 distinct weeks with ≥50% confidence; trigger
precision 0.90 (GeoLife), 97–99% (brightkite 683/692, gowalla 62/64).

### Π ceiling per regime (dataset_summary)

geolife 0.55 all / 0.64 cohort · yjmob1 0.63 · yjmob2 0.62 · fsq_nyc 0.58 ·
fsq_tky 0.59 · gowalla 0.43 · brightkite 0.65 — and the best baseline flips by
regime (Markov on GPS/grid vs frequency/time-of-week on check-ins).

## Conclusions — the agreed demo

**Tier-2 static site** (user-confirmed): Vite + Svelte 5 (compiles away, no
framework runtime) + GSAP/ScrollTrigger scrollytelling + modular D3 + MapLibre GL
with a custom dark style (CARTO dark raster underlay when online, data layers only
when offline). One build script (`scripts/build_demo.py`, uv/python) reads the
parquets and emits `demo/public/data.json` + real H3 hexagon GeoJSON via the
project's `h3` package — nothing hand-drawn. Payload budget < ~1 MB, no freeze.

Nine sections: hero count-ups → dataset gallery → noise-to-places funnel →
**H3 hexagon scene** (why hexagons, r9→r8 zoom ladder, 0.10→0.74 km², honest ~7%
nesting gotcha) → **15-minute bucket scene** (96 slots/day, 672 weekly slots,
interactive 5/15/60-min resolution comparison) → entropy guessing-game (zero
equations) → pattern-detection rates + confidence → interactive weekday/time
trigger with route → honest punchline (predictability tracks how you're watched).

Protagonist: GeoLife user 022 (Π 0.864, 13 places, real "Mon 15:00–15:15" card).
Plain-language copy throughout (numbers always captioned in words).
Effort: `efforts/2026-11-01-static-demo-website/` (SDD).
