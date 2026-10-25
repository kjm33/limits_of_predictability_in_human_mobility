# Demo curation — what the dashboard will show (2026-10-23)

Companion to `notebooks/07_demo_curation.ipynb`, which materialises the curated package the
upcoming Streamlit dashboard (`efforts/2026-10-23-predictability-dashboard/`) renders. The
dashboard is a **thin rendering layer**: it loads only `data/processed/dashboard/` and never
touches the 180M-row `seq_hourly` panels upstream.

---

## What we present and why

**1. The headline Π story — one row per dataset.** The dashboard's headline number is
**Π_actual** — the Fano ceiling from the LZ *actual* entropy — because Song et al. (2010)'s
famous 0.93 is exactly that inversion on their phone data: the apples-to-apples number the
project re-examines. The three predictabilities are ordered, Π_rand ≤ Π_unc ≤ Π_actual
(entropies are non-increasing: S_rand ≥ S_unc ≥ S_actual, since shuffling can't create
order and ignoring order can't reveal it; the Fano inversion is decreasing in entropy, so
the ceilings are non-decreasing). Against Song's 0.93: **GeoLife Π_actual median 0.553 /
mean 0.548 (0.637 in its curated 76-user cohort), YJMob100K mean 0.633 (split 1)**, with
the Π_actual median spanning **0.437 (Gowalla) → 0.654 (Brightkite)** across four sensing
technologies — under honest missingness the ceiling is ~2/3 everywhere. The frequency-only
bound Π_unc stays in a narrow 0.33–0.49 band: what separates datasets is the *order
dividend* (Π_actual − Π_unc), not destination inventory. And density is not predictability:
YJMob100K is the best-sensed panel (q ≈ 0.60–0.62 vs 0.90–0.98 elsewhere) yet sits
mid-pack (Π_actual median 0.625–0.639). The dashboard leads with this table plus Π
distributions from the user-level panel (243,800 rows).

**2. The winner flips.** No model family wins twice:

| dataset | best overall (top-1) | source |
|---|---|---|
| geolife | temporal_transformer 0.235 (markov2_col 0.228 close 2nd) | deep |
| yjmob1 | markov1 0.287 | baseline |
| yjmob2 | markov1 0.226 (transformer only 0.135) | baseline |
| fsq_nyc | rw_trip_dest 0.299 (best baseline `time` 0.286) | rw |
| fsq_tky | freq 0.273 (rw 0.261, deep 0.254 close behind) | baseline |
| gowalla | time 0.176 | baseline |
| brightkite | markov1_col 0.511 (best deep only 0.298) | baseline |

Deep learning earns its complexity only on the richest GPS traces; first-order Markov
crushes it on dense grids; the venue-graph random walk wins where timestamps are sparse.
Hence the dashboard ships the **full leaderboard per dataset** (81 model rows), not a
global champion badge.

**3. Featured users — deterministic editorial picks.** Zoom-in stories must be
reproducible, not hand-picked (rules in the notebook, §5). Each pick carries its own
per-user extract directory so the dashboard's user view loads in single-digit
milliseconds.

## Curated package schemas (`data/processed/dashboard/`)

- **`dataset_summary.parquet`** — 7 rows, one per dataset.
  `dataset, n_users, n_cohort, q_median, n_median, s_unc_median, pi_unc_median,
  pi_unc_mean, pi_actual_median, pi_actual_mean, fano_frac, best_baseline,
  best_baseline_top1, n_cards, n_places`. Landing-page headline — **`pi_actual_*` is the
  Song-comparable headline**; `pi_unc_*` is the frequency-only lower-bound context.
  `q_median` = share of unknown hourly slots (higher = sparser); `fano_frac` = **Fano
  compliance**, the share of users with Π_actual ≥ Π_unc as the entropy ordering demands
  (ties compliant; users with undefined Π excluded): 1.000 on both yjmob grids, 0.992–0.996
  on Foursquare, 0.976 Brightkite, 0.934 GeoLife; Gowalla's 0.860 is its never-revisiting
  users at the Fano inversion's numerical floor — render with a small-N caveat, not hidden.
  `best_baseline_top1` is the n_eval-weighted top-1.
- **`pi_distributions.parquet`** — 243,800 rows, one per (dataset, user).
  `dataset, user, N, S_rand, S_unc, S_actual, Pi_rand, Pi_unc, Pi_actual, q` (`q` NA when
  seq_q lacks the user). Histograms, box plots, Π-vs-q scatter.
- **`leaderboards.parquet`** — 81 rows, one per (dataset, model).
  `dataset, model, source, n_users, n_eval_sum, top1, top3, dist_km`; `source` ∈
  `baseline` / `rw` / `deep` (rw absent for yjmob, deep absent for yjmob1). All metrics
  are n_eval-weighted means of per-user values, mapped onto the shared scheme.
- **`featured_users.parquet`** — 15 rows, one per pick.
  `dataset, user, why, Pi_unc, Pi_actual, N, q, n_cards, n_places`.
- **`users/<dataset>/<user>/`** — one dir per pick:
  - `seq.parquet` — `user, hour, cell_idx, h3, weekday, hour_of_day, lat, lon, known`
    (`known` = `cell_idx != -1`; `lat/lon` joined from `cells_r8` on `h3`);
  - `cards.parquet` — routine-card rows for the user (empty-but-typed where the stage
    didn't run);
  - `places.parquet` — the user's `places_summary` rows;
  - `poi.parquet` — **yjmob only**: the 85 `poi_*` category counts summed over the user's
    distinct known r8 cells, one row (written only when non-empty).

Package total: 53 parquets, ~12 MB.

## Featured picks (15) and rationale

| dataset | user | why | Π_actual | N | n_cards | story |
|---|---|---|---|---|---|---|
| geolife | 022 | most_predictable | 0.864 | 104 | 1 | also the routing/suggest demo user — flagship |
| geolife | 111 | most_exploratory | 0.225 | 194 | 1 | richest trace, least order |
| yjmob1 | 66750 | most_predictable | 0.951 | 152 | 0 | densest sensing, near-deterministic life |
| yjmob1 | 29085 | most_exploratory | 0.202 | 316 | 0 | 316 distinct cells, still unpredictable |
| yjmob2 | 8872 | most_predictable | 0.924 | 165 | 0 | |
| yjmob2 | 4057 | most_exploratory | 0.242 | 378 | 0 | |
| fsq_nyc | 185 | most_predictable | 0.855 | 63 | 0 | venue check-ins, extreme regularity |
| fsq_nyc | 882 | most_exploratory | 0.274 | 50 | 0 | |
| fsq_tky | 2132 | most_predictable | 0.908 | 42 | 0 | |
| fsq_tky | 2182 | most_exploratory | 0.272 | 45 | 0 | |
| gowalla | 19917 | most_predictable | 0.970 | 22 | 0 | tiny inventory, perfectly repetitive |
| gowalla | 77759 | most_exploratory | 0.024 | 41 | 0 | never revisits a cell (Π floor) |
| brightkite | 206 | most_predictable | 0.997 | 42 | 0 | highest Π among covered users (N ≥ 41; tiny-N users score higher but are artifacts) |
| brightkite | 22029 | most_exploratory | 0.106 | 145 | 0 | |
| brightkite | 9957 | routine_creature | n/a | 1 | 39 | most routine cards in any dataset; Π undefined (single r8 cell, 39 places inside it) — the cards panel is the story |

Selection rules (deterministic, tie-broken by ascending user id): per dataset, among users
with `N >=` dataset median N and computable Π_actual, the highest-Π user is
`most_predictable` and the lowest-Π user is `most_exploratory`; geolife `022` is always
present (this run it *is* geolife's most predictable user, so its rule-1 row stands in for
`suggest_flagship`); brightkite's most-carded user becomes `routine_creature`.

## How to refresh

Re-run the notebook — it rebuilds `data/processed/dashboard/` from scratch (idempotent):

```bash
uv run jupyter nbconvert --to notebook --execute --inplace notebooks/07_demo_curation.ipynb
```

Upstream dependencies (re-run these first if they change): `entropy`, `baselines`,
`routines`, `graphs` stages per dataset (plus `yjmob`/`checkins` adapters). Everything the
package contains is derived from `entropy/seq_q/cohort/baseline_hourly_results/rw_results/
deep_results/routines/places_summary/cells_r8/seq_hourly/poi` parquets; no `src/` changes
are involved. The notebook's §7 verification re-loads the whole package, asserts schemas
and grains, and times a worst-case (yjmob1) featured-user load (< 1 s; actual: single-digit
milliseconds).
