# Results in Plain Language — 2026-10-12

A no-jargon summary of what this project did, what worked, and what didn't.
(Technical companion: `research-2026-10-12.md`; figures: `reports/`.)

## What we did

**Data used:** GeoLife — 182 people in Beijing carrying GPS loggers (2007–2012),
~25 million GPS points. We compressed this into "where did each person stop for
10+ minutes" (23,348 stops) and "what trips did they take" (23,169 trips).
Only 76 people had enough consistent data for the serious analysis.

## The three questions we asked

### 1. "How predictable are these people, in theory?" (Song et al. 2010 reproduction)

We measured three kinds of disorder in each person's location history:

- **Random entropy** — if their behavior were pure chaos
- **Uncorrelated entropy** — if each location choice were independent of the last
- **Actual entropy** — accounting for full patterns and habits (compressed out
  real regularities)

**Result: partially reproduced.** People's actual entropy was much lower than
random — habits are real. But our theoretical predictability ceiling came out at
**~0.64** for the good users, vs the paper's famous **93%**. Why the gap?
The paper used phone records logged every hour like clockwork; GeoLife users
turned their GPS on and off unpredictably (we could only "see" them ~84% of
waking hours at best, most far less). Sporadic observation makes people look
more random than they are. Also, 93% of our users stayed under their Fano
theoretical limit — the math held up.

### 2. "How well can simple models actually predict the next location?"

- Most-frequent-location: **18%** accurate
- Markov chains ("you usually go X after Y"): **23%** — best simple model,
  using everyone's data pooled together
- Fancy deep models (LSTM, Transformer): **Transformer won at 26%** — a real
  but modest gain over Markov, about one extra correct guess in thirty
- A graph neural network approach: **failed badly (2%)** — the simplified
  version we built couldn't handle 5,000+ possible locations
- A graph random-walk predictor beat a simple Markov model on trip
  destinations (18% vs 15%)

**Takeaway:** with only ~76 users of sparse data, deep learning barely beats
counting patterns. The predictability ceiling (~0.64) is far above what any
model achieved (~0.26) — lots of headroom, but hard to reach with this data
volume.

### 3. "Can we build the 'Thursday 15:15' assistant?"

Yes — this was the biggest practical success. We mined recurring weekly
routines (e.g., "Mondays around 15:00, user 022 goes from home to a specific
spot") and built a trigger: given the current time and where you are, predict
where you're about to go and show the route (via OSRM).

- Found **244 solid routines** across 34 users
- When the assistant fired, it was right **90% of the time**
- But it could only fire for people with strong routines — most users
  (154/176) never triggered it

## What worked / what didn't

**Worked:** entropy theory (with caveats), Markov baselines, routine mining +
trigger rule, the routing demo.

**Didn't:** reaching the paper's 93% (data too sparse — honestly explained in
notebook 02, not hidden), the graph neural net (too simplified), deep models'
distance errors were worse than Markov's.

All of this is written up with figures in `notebooks/01-06` and `reports/`,
with an honest README summarizing the same story.
