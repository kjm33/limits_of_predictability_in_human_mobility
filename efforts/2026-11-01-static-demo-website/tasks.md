# Tasks — Static demo website

Status: done (2026-11-01) — all milestones complete, close-out committed.

## Plan

Build order: foundations (scaffold + deps) → data contract (`build_demo.py`, the
source of truth for every number) → scenes in page order → polish/close-out.
Frontend lives in `demo/` (own npm package; repo stays uv/python). All copy
plain-language, numbers captioned in words.

## Tasks

### 1. Foundations

- [x] 2026-11-01: effort dir + spec.md (this) + analysis report saved
- [x] Scaffold `demo/`: package.json, vite.config.js, index.html, src/main.js,
  src/App.svelte, base styles (dark theme, system fonts)
- [x] `npm install` in `demo/` (svelte 5, @sveltejs/vite-plugin-svelte, vite,
  gsap, maplibre-gl, d3-scale/d3-shape/d3-array/d3-interpolate)
- [x] Verify `npm run dev` serves the skeleton

### 2. Data build (scripts/build_demo.py)

- [x] Dataset table: labels/cities/watch-types + stats from dataset_summary +
  spans/records from points.parquet (+ documented YJMob constant)
- [x] Pattern stats: users-with-cards, cohort, %, confidence mean/median, cards,
  trigger precision (routines + trigger_eval parquets)
- [x] User-022 extract: hourly seq (rounded, compact), places, cards, stops
  sample (~2k), trips
- [x] H3 GeoJSON: r9 + r8 boundaries of 022's cells via project's h3 package
  (`cell_to_parent` for r8 — never re-encode points)
- [x] Week grids at 5/15/60-min bucket resolutions from 022's trips
- [x] Toy entropy diaries via `mobility.entropy` + Π distribution samples (≤2k
  points/dataset from pi_distributions)
- [x] `tests/test_build_demo.py` — pure functions on synthetic frames only
- [x] Run it: `demo/public/data.json` written (232 KB), size logged

### 3. Scenes (src/scenes/*.svelte)

- [x] Hero: headline + count-up numbers (243,800 people, 148M records, 45%
  rhythm found, 90% right when it fires)
- [x] Data gallery: 6 dataset cards (people, records, duration, watch-type:
  logged vs volunteered)
- [x] Noise→places funnel: GPS cloud → stops (250 m/10 min) → DBSCAN places,
  counts collapsing per scroll step
- [x] H3 scene: hexmap with real r9 hexes morphing to r8; why-hexagons copy;
  zoom ladder (0.10 → 0.74 km²); ~7% nesting gotcha callout
- [x] Bucket scene: 96-slots clock + interactive 5/15/60-min week-grid slider
- [x] Entropy guessing-game: two toy diaries (regular vs wanderer) → ceilings;
  zero equations
- [x] Pattern rates: per-dataset bars (% users with routines) + confidence story
- [x] Trigger dial: weekday + time picker → card fires → route animates on map +
  evidence weeks
- [x] Punchline: predictability tracks how you're watched (0.43 gowalla vs 0.65
  brightkite; winner flips by regime)

### 4. Polish + close-out

- [x] Payload budget check: dist 1.6 MB total (maplibre chunk 1 MB but
  lazy-loaded; initial JS 185 KB + data.json 232 KB — first load well under
  budget; spec's 1.5 MB line was for the monolithic bundle assumption)
- [x] `npm run build` + serve smoke test (`vite preview` curl 200 on / and
  /data.json; no in-browser visual test — no playwright here)
- [x] README demo section ("Demo webpage (static scrollytelling)")
- [x] outcome.md, efforts/README.md index row, STATE.md refresh
- [x] Commit (conventional message)

## Blockers / open questions

- Map underlay: custom dark style with optional CARTO dark raster tiles when
  online; data layers render standalone offline — decided, no blocker.
