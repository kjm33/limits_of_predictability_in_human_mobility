# Outcome — Static demo website (plain language)

## What we did

We replaced the "heavy + jargon" Streamlit first impression with a lightweight
static webpage that tells the whole story by scrolling: 6 datasets → how raw GPS
noise becomes places (H3 hexagons + 15-minute buckets) → how predictable people
are → a live weekday+time trigger that fires a real routine card for user 022
(Mon 15:00, home → place#3). One Python script (`scripts/build_demo.py`) reads
the parquets and writes a single 232 KB `data.json`; the page is a Vite +
Svelte 5 app with GSAP scroll animations and a MapLibre hexmap. Nothing is
computed in the browser — every number on the page comes from the data.

## What worked

- **The payload promise held**: first load is ~420 KB of wire (185 KB app JS +
  232 KB data); the 1 MB MapLibre library loads lazily only when the map scene
  approaches. No freeze, no framework runtime.
- **All 9 scenes render and build clean**: `npm run build` succeeds, preview
  serves 200, 143 tests green (9 new synthetic tests for the build script's
  pure functions), ruff clean.
- **The numbers survived the trip**: hero counts (243,800 people, 148M records,
  45% rhythm found on GeoLife, 90% trigger precision) each cross-checked
  against the parquets during development; the trigger dial fires exactly at
  Mon 15:00 because 022's real week-grid slot says cell 46 on 4 of his weeks.
- **Plain language everywhere**: entropy is a guessing game (no equations),
  H3's ~7% nesting quirk is a "credibility moment" callout, every stat gets a
  words caption ("about one error per eight words"-style).

## What didn't

- **No in-browser visual test** — no playwright in this environment; we
  verified compile + serve + data fields, not pixels. A human should scroll it
  once (`cd demo && npm run dev`).
- **Total dist is 1.6 MB vs the spec's ~1.5 MB line** — entirely the lazily
  loaded MapLibre chunk; first paint stays well under budget, so we kept it.
- Brightkite/gowalla cards carry no venue labels (check-in datasets) — the
  trigger story is told on GeoLife 022 only, which is also a scope choice, not
  a bug.

## Bottom line

There is now a public-facing one-page story where the "enigma" is the
punchline: predictability tracks how you're watched (Π 0.43 gowalla → 0.65
brightkite, and the winning model flips with the regime). Rebuild anytime with
`uv run python scripts/build_demo.py`; view with `cd demo && npm run dev`.
Research dashboard untouched.
