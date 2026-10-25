# Tasks — Demo curation

**Status: DONE 2026-10-23** — see outcome.md. Review catch: headline Π must be Π_actual
(Song-comparable), not Π_unc; fano_frac direction fixed.

## Plan

1. Start only after `2026-10-23-checkin-routines-graphs` closes.
2. Notebook 07: load all six datasets' entropy/baseline/deep/routine outputs; compute
   headline table; select featured users (criteria documented); write curated parquets
   to `data/processed/dashboard/`.
3. Write `notes/2026-10-23-demo-curation.md` with rationale + schema docs.
4. Acceptance commands; close out.

## Tasks

- [x] notebook 07 skeleton: per-dataset loader cells + headline table
- [x] featured-user selection + rationale (15 picks: most_predictable/most_exploratory ×7,
      suggest_flagship 022 absorbed into geolife most_predictable, routine_creature bk 9957)
- [x] curated parquets written to data/processed/dashboard/ (53 files, ~12 MB; headline
      table, 243k-row Π table, 81-row leaderboard, per-user extracts incl. yjmob POI)
- [x] notes/2026-10-23-demo-curation.md
- [x] acceptance: nbconvert execute + pytest + ruff green
- [x] review fix: headline = Π_actual (Song-comparable) not Π_unc; fano_frac =
      frac(Π_actual ≥ Π_unc) (was inverted); trio explanation added

## Blockers / open questions

- none yet
