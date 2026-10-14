# New Datasets: Results — 2026-10-14

What happened when we stopped relying on GeoLife alone and wired in three more
human-mobility datasets. Plain-language companion to
`2026-10-12-results-plain.md`; the motivation research is in
`2026-10-13-research-datasets.md`.

## Why we did this

GeoLife's core limitation was never the models — it was the data. Median user
is "seen" in only ~9% of hours (q = 0.905), only 76 of 182 users pass the
cohort bar, and deep models train on ~48.5k windows over 5,364 classes.
Every interesting negative result ("transformer barely beats Markov",
"GraphSeq collapses") had a footnote: *maybe there just wasn't enough data.*
The new datasets attack exactly that: more users, denser observation,
different cities and sensing regimes.

## The three newcomers

| Dataset | What it is | Users | Hourly panel | Coverage q | Cohort |
|---|---|---|---|---|---|
| YJMob100K (ds1) | App-location pings, Japanese metro, 500 m grid, 75 days, 30-min slots | 100,000 | 180,000,000 h | 0.594 | 99,974 |
| YJMob100K (ds2) | Same regime, 25k users, incl. 15-day emergency period | 25,000 | 45,000,000 h | 0.576 | 24,997 |
| Foursquare NYC | Venue check-ins w/ categories, ~10 months | 1,083 | 6,836,751 h | 0.971 | 62 |
| Foursquare Tokyo | same | 2,293 | 15,091,683 h | 0.972 | 494 |
| Gowalla | Location check-ins + friendship graph, ~20 months | 107,069 | 231,330,049 h | 0.886 | (pending) |
| Brightkite (>=100 check-ins) | Location check-ins + friendship graph | (pending) | (pending) | (pending) | (pending) |

Notes: q = fraction of a user's enrolled hours with unknown location (lower =
denser). Gowalla kept unfiltered (documented mixed policy); Brightkite
filtered to users with >=100 check-ins (DeepMove-style) to bound panel memory.

## Headline: the predictability ceiling is robust, the sparsity excuse isn't

The single most important number this project produced on GeoLife was the
Fano predictability ceiling Π ≈ 0.64 — far below the famous 0.93 of Song et
al. (2010). The honest worry: maybe 0.64 was just an artifact of GeoLife's
terrible coverage (q = 0.905), since Π correlated with q across users.

YJMob100K answers it: with **q = 0.594** — six times denser observation,
1,300× more users — the ceiling comes out at **Π ≈ 0.633 mean (0.639 median)**
for dataset1 and **0.625 median** for dataset2. Essentially the same 0.63-0.64
as GeoLife's cohort. The ceiling does *not* recover toward 0.93 when you feed
it dense, massive data — if anything the GeoLife estimate wasn't a fluke;
it's the tower-resolution regime of the original paper that sits near 0.93.
Predictability ~0.6 looks like a property of *this kind of urban
location data*, not of our sample size.

Check-in datasets sit lower still: Foursquare NYC Π = 0.576, Tokyo 0.593.
Venue check-ins are burstier and more voluntary than app pings — people
check in at restaurants, not at home.

## Baselines: the winner flips by sensing regime

(TODO: yjmob1/yjmob2/gowalla/brightkite tables from queue v2.)

On GeoLife, collective Markov (order 3) won hourly next-cell prediction
(0.231 top-1). On Foursquare check-ins the ranking inverts: simple
per-user **frequency** and **time-conditioned** baselines beat Markov
(NYC: time 0.254 / freq 0.241; TKY: freq 0.264 / markov1 0.253). Check-in
sequences are short and repetitive; transition context adds nothing —
the opposite of dense GPS trajectories. Distance errors are ~5 km (vs
110 km on GeoLife's Beijing-scale cells) — urban-scale, useful.

## Deep models: still data-limited, now with a cleaner verdict

(TODO: gowalla/brightkite/yjmob2 deep results.)

On Foursquare, 1-epoch transformer: NYC 0.198, TKY 0.237 — both *below* the
frequency baseline. GraphSeq collapsed again (0.005 / 0.04). With GeoLife the
story was "deep barely beats counting"; on check-ins it's "deep doesn't beat
counting at all." YJMob100K (the only dataset with enough windows to matter)
is where this question actually gets settled — see queue results.

## Infrastructure: what it took

- **Adapters, not rewrites.** YJMob100K bypasses GPS ingest entirely (it's
  pre-discretized) and writes the shared hourly-panel schema directly;
  Foursquare/SNAP check-ins reuse the points→stays→sequences chain with a
  new parser + user-aware QC.
- **Two-pass sharded baselines.** 100k users × 180M hourly rows OOM-kills the
  monolithic evaluator (40+ GB). The sharded path streams the parquet once to
  pool collective Markov counts into compact numpy tables, then evaluates
  user-shards independently — bit-identical results (test-verified),
  bounded memory (~9 GB/shard-set).
- **Cgroup containment.** Every heavy stage runs under
  `systemd-run --user --scope -p MemoryMax=38G` — a stage that overruns is
  killed *alone*; the session and the rest of the queue survive. (See
  postmortem below.)

## OOM postmortem (what killed 5+ sessions)

1. Plain `nohup ... &` jobs die with session teardown (SIGHUP).
2. `setsid` survives SIGHUP but not the kernel OOM killer.
3. Monolithic `run_baselines` on yjmob1 needs 40-50+ GB (Markov context
   copies + collective tables + per-user state for 100k users). The box is
   shared (LLM training/serving jobs come and go, ~8-17 GB) — real budget
   ~45-50 GB, so 62 GB total was never actually ours.
4. When the kernel OOM fires it kills multiple victims, including the
   interactive session. Fix, in order: serialize stages; cap each stage in
   its own cgroup; make the big stage's memory O(rows/shards), not O(rows).

## Honest caveats

- YJMob100K is pre-discretized: no raw GPS, masked dates/city — stay
  detection, routines, routing/suggest and real-km distances don't apply;
  distances are grid-cell based (500 m cells).
- Brightkite's >=100-check-in filter (vs Gowalla unfiltered) is a memory
  compromise, not science; documented, and the sequences stage flag
  (`--min-points`) makes it reproducible either way.
- yjmob1 deep training was skipped (CPU-only torch on 180M-hour panel is
  prohibitive); deep runs cover yjmob2, fsq, gowalla, brightkite.
- Foursquare cohort is small (62 NYC / 494 TKY users) — check-in data is
  inherently sparse per user (q ≈ 0.97); entropy numbers there are for
  contrast, not headline claims.
