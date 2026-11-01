# Spec — Static demo website (scrollytelling)

Status: done
Start: 2026-11-01
End: 2026-11-01
Analysis/report: `reports/2026-11-01-demo-website-analysis.md`

## Goal

Replace the "heavy + jargon" Streamlit first impression with a **lightweight static
scrollytelling webpage** that anyone can understand: present the data collected
(6 datasets, ~240k people), the core statistics (users, duration, sensing regime),
the pattern-detection results (% of users with weekly routines, confidence), and the
weekday/time trigger — with strong explainer scenes for the two preprocessing ideas
the user wants highlighted: **Uber's H3 hexagonal grid** and **15-minute buckets**.

## Expected results

- `demo/` — Vite + Svelte 5 + GSAP/ScrollTrigger + modular D3 + MapLibre GL app,
  9 scrollytelling sections (hero · datasets · noise→places · H3 · buckets ·
  entropy-guessing-game · pattern rates · trigger dial · punchline), dark theme,
  plain-language copy with every number captioned in words.
- `scripts/build_demo.py` — uv/python build script reading `data/processed/`
  parquets (incl. curated `dashboard/` extracts) → emits `demo/public/data.json`:
  dataset table, pattern/confidence stats, user-022 extracts (seq/places/cards/
  stops/trips), real H3 r9/r8 hexagon GeoJSON, week-grid matrices at 5/15/60-min
  resolutions, Π distribution samples, toy entropy diaries computed with
  `mobility.entropy`.
- Interactive scenes: count-up hero, hexmap morph (r9→r8), bucket resolution slider
  (5 vs 15 vs 60 min), weekday+time trigger dial with route animation on the map.
- Payload budget: `demo/dist` < ~1.5 MB total (excluding optional online raster
  tiles); zero framework runtime shipped; no browser freeze.

## Non-goals

- Not replacing the Streamlit research dashboard (`dashboard/`, stays as-is).
- No server, no backend, no new pipeline analysis or model changes.
- No multi-language, no mobile-app, no WebGL/globe (Tier 3 rejected).

## Acceptance criteria

1. `uv run pytest -q` green (incl. a new synthetic-data test for `build_demo.py`
   pure functions).
2. `uv run ruff check src tests scripts` clean.
3. `uv run python scripts/build_demo.py` runs on real data and writes
   `demo/public/data.json` (schema-documented at top of script).
4. `cd demo && npm ci && npm run build` succeeds; built site served and every
   section renders (curl or preview 200 + no console-error smoke check).
5. `du -sh demo/dist` ≲ 1.5 MB and `data.json` ≲ ~800 KB.
6. Close-out: outcome.md + efforts/README row + STATE.md refreshed + README demo
   section, committed.
