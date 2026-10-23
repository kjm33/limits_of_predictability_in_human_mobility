# GeoLife pipeline — predictability analysis + proactive route suggestion

Status: done
Start: 2026-10-12
End: 2026-10-12

> Retrofitted 2026-10-23 from `tasks.md` (originally `plans/plan.md`), `notes/2026-10-12-research.md`,
> commits 259e283…8d0abb4, and `outcome.md`. Acceptance criteria recorded "as was" — what would
> have verified this effort when it ran.

## Goal

Reproduce Song et al. (Science, 2010) limits-of-predictability analysis on GeoLife (182 users,
Beijing GPS, 2007–2012) and build a pipeline from raw GPS through H3 cells, entropy, baselines,
routines, graphs and deep models to a proactive route-suggestion demo ("every Thursday 15:15 the
user drives to music school").

## Expected results

- `src/mobility/` modules for all 7 phases, each runnable via `python -m mobility.<module>`
- Per-user entropy trio (S_rand / S_unc / LZ actual) + Fano Π, honestly compared to the paper's 93%
- Statistical baselines: frequency, time-conditioned, Markov 1–3 (individual + collective)
- Routine cards + trigger rule with precision/recall evaluation
- Per-user/global transition graphs + random-walk predictor; deep models (DeepMove-style RNN,
  Transformer, GraphSeq) with fair comparison vs baselines
- `mobility.suggest` CLI producing folium route maps; executed notebooks 01–06 + figures in `reports/`

## Non-goals

- Matching the paper's 93% Π headline (GeoLife's hourly grid is far sparser; documented, not chased)
- GPU training (torch CPU only), real-time inference, datasets beyond GeoLife (later effort:
  2026-10-13-multi-dataset-extension)

## Acceptance criteria (as was)

- [x] `uv run pytest` green (114 tests, synthetic data only, network mocked)
- [x] `uv run ruff check src tests` clean
- [x] All 7 phase modules run in order on real GeoLife data → parquet outputs in `data/processed/`
- [x] Notebooks 01–06 executed with embedded outputs; figures committed to `reports/`
- [x] `python -m mobility.suggest --user 022 --now "Mon 15:14" --route` produces a route map

## References

- `outcome.md` (was `notes/2026-10-12-results-plain.md`) — plain-language results
- `notes/2026-10-12-research.md` — method background (Song 2010)
- `reports/` figures; `notebooks/01-06`; README headline-results table
