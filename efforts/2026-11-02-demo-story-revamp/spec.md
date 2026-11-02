# Spec — Demo story revamp: inspiration → on-device agent

Status: done (approved in plan mode, implemented + verified same day)
Start: 2026-11-02 · End: 2026-11-02

## Goal

Restructure the static demo (`demo/`) into a narrative that runs from the
inspiration (Song et al. 2010, `research/Limits of Predictability in Human
mobility.pdf`) to the application: a proactive, local-first navigation agent.
All copy stays scientifically accurate; numbers stay sourced from
`data.json` / the paper (facts re-verified from the PDF text: 50,000 users
from ~10M screened to 45,000 with q<0.8, 3-month tower records, hourly
sequences, 93% mean Π_max via entropy + Fano; the paper builds no predictor).

## Expected results

New scene order (12 scenes), user-approved:

1. Hero — reframed as the inspiration: Song et al. 2010 + its headline, kept
   project-scale count-ups; 93% clearly labelled as the paper's estimated
   ceiling for tower data, not achieved accuracy.
2. Goal (NEW `Goal.svelte`) — proactive navigation agent; on-device framing:
   location history never needs to leave the device; simple counting methods;
   edge-device suitability stated as a design goal, not a measured result.
3. DataGallery — unchanged content.
4. Discretize — moved up as the continuous→discrete overview.
5. Funnel — unchanged.
6. HexMap — + one line distinguishing our H3 cells from the paper's towers.
7. BucketClock — + note: routines use quarter-hours, the entropy/predictability
   analysis uses hourly sequences (the paper's choice).
8. GzipWalk — before the guessing game now: remove forward reference, frame
   gzip as the analogy (real estimator = Lempel-Ziv block counting, as in the
   paper's SOM), add "low leftover surprise → worth predicting" selection idea.
9. GuessGame — + explicit Fano selection copy (keep high-ceiling users as
   promising candidates; ceiling ≠ achieved accuracy); fix stale "next
   section" wording.
10. PatternBars — unchanged.
11. Punchline — moved before the finale; kicker → results; bridges to finale.
12. TriggerDial — reworked from "The payoff" into the proactive-agent finale:
    context → rule fires with evidence → route offer; on-device note; honest
    trigger caveat kept.

`demo/src/App.svelte` SECTIONS + imports reordered accordingly; README demo
section list refreshed; STATE.md scene count updated.

## Non-goals

- No changes to `scripts/build_demo.py` / data.json (no new numbers needed).
- No map library, no new dependencies, no new interactive visualizations
  beyond copy/panels in existing style.
- Not claiming offline routing or on-device benchmarks; privacy copy covers
  location-history analysis only (routing service caveat in fine print).

## Acceptance criteria

- `cd demo && npm run build` succeeds.
- `uv run pytest -q` green, `uv run ruff check src tests scripts dashboard`
  clean (Python untouched; regression guard).
- Page contains 12 nav dots in the new order; no scene text forward-references
  a scene that no longer follows it.
