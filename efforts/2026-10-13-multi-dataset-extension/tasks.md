# Tasks — Multi-dataset extension

Status: done (2026-10-13 → 2026-10-23)

> Retrofitted 2026-10-23. This effort had no live plan file — tasks below are reconstructed
> from the git log (3a86273…3454774) and the dated research/results notes.

## Plan

(Retrofitted) Driven by `research.md`: pick datasets that attack GeoLife's sparsity/cohort/
data-volume bottlenecks, make every stage dataset-agnostic, then run entropy/baselines/deep
across all of them and compare Π.

## Tasks

- [x] 2026-10-13: Dataset requirements research → `research.md`
- [x] 2026-10-14: Dataset-agnostic stages — `processed_dir` threading + sparse-panel guard (3a86273)
- [x] 2026-10-14: YJMob100K + Foursquare/SNAP check-in adapters, fetch scripts, `run_stage` CLI (3cc461f)
- [x] 2026-10-14: New-datasets results note (c91579f; later extended)
- [x] 2026-10-23: GraphSeq guard — skip above 40k-cell vocab (dense PPR would need ~13 GB) (92630d7)
- [x] 2026-10-23: README datasets overview (6 datasets) + Gowalla/Brightkite entropy results —
      Π tracks sensing regime, not density (3454774)

## Blockers / open questions

- yjmob1 deep training skipped (CPU-only torch) → `../../BACKLOG.md`
- Brightkite ≥100-check-in filter is a memory compromise → `../../BACKLOG.md`
- Research-goal analyses not pursued (friendship graphs, disruption, DeepMove benchmark) → `../../BACKLOG.md`
