# Multi-dataset extension — YJMob100K, Foursquare, Gowalla, Brightkite

Status: done
Start: 2026-10-13
End: 2026-10-23

> Retrofitted 2026-10-23 from `research.md` (motivation + dataset requirements, was
> `notes/2026-10-13-research-datasets.md`), `outcome.md` (results, was
> `notes/2026-10-14-new-datasets-results.md`), and commits 3a86273, 3cc461f, c91579f,
> 92630d7, 3454774. No live plan file existed for this effort; tasks.md was reconstructed
> from the git log.

## Goal

Fix GeoLife's documented bottlenecks (hourly sparsity q ≈ 0.905, 76-user cohort,
data-starved deep models) by wiring three more open mobility-dataset families
(YJMob100K grid, Foursquare TSMC2014, SNAP Gowalla/Brightkite check-ins — 6 dataset keys)
into the same downstream stack, and test whether Π ≈ 0.64 was a data-density artefact.

## Expected results

- Dataset-agnostic stages: every stage function takes `processed_dir=`; new
  `scripts/run_stage.py <stage> --dataset <key>` CLI wires any stage to any dataset
- Adapters: `mobility.yjmob` (pre-discretized grid, no raw GPS), `mobility.checkins`
  (TSMC2014 + SNAP), fetch scripts for all raw sources
- Per-dataset processed trees `data/processed/<key>/`
- Cross-dataset entropy/Π and baseline/deep comparisons answering the density question

## Non-goals

- Stay detection / routines / routing on pre-discretized YJMob100K (no raw GPS)
- yjmob1 deep training (CPU-only torch on a 180M-hour panel is prohibitive) → BACKLOG
- GPU acceleration; new model architectures

## Acceptance criteria (as was)

- [x] `uv run pytest -q` green incl. adapter tests (synthetic fixtures, network mocked)
- [x] `uv run ruff check src tests scripts` clean
- [x] `scripts/run_stage.py <stage> --dataset <key>` works for all 6 keys
  (`yjmob1`, `yjmob2`, `fsq_nyc`, `fsq_tky`, `gowalla`, `brightkite`)
- [x] Cross-dataset Π tables in `outcome.md` + datasets section in README

## References

- `research.md` — motivation, GeoLife bottleneck evidence, dataset requirements
- `outcome.md` — cross-dataset results + honest caveats; OOM postmortem (cgroup discipline)
- AGENTS.md module map (`yjmob`, `checkins` rows)
