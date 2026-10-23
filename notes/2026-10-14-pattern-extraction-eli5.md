# How User Patterns Were Extracted — ELI5 Walkthrough (2026-10-14)

A plain-language, step-by-step companion to `../efforts/2026-10-12-geolife-pipeline/outcome.md`, grounded in
the actual source code. Covers the full extraction funnel, then deep-dives into the six
things most worth understanding: the compression (LZ) entropy trick, Fano's inequality,
15-minute buckets, routine-card matching, Markov backoff, and where the routine
assistant's confidence comes from.

---

## Part 1 — The extraction funnel (raw GPS → patterns)

**Step 0 — Clean the raw noise** (`src/mobility/ingest.py`)
25M GPS points from 182 people. Drop impossible points (speed > 324 km/h), cut
trajectories into segments wherever the logger was off for > 20 min. Gaps are treated
as "we couldn't see them", never as "they stayed put".

**Step 1 — Find where people actually stopped** (`stay.py:32`)
Bucket positions into 1-minute medians (kills GPS jitter), then slide a window: from an
anchor point, keep extending while every new point stays within **250 m** of the running
center. If the cluster covers **>= 10 minutes**, it's a real "stop". Nearby repeats get
merged; consecutive stops become "trips" (origin → destination).
Result: 23,348 stops, 23,169 trips.

**Step 2 — Turn stops into named "places"** (`routines.py:21`)
Per user, DBSCAN clusters stop centroids (300 m) into recurring places; stray stops snap
to the nearest cluster. Two heuristic labels: most **nighttime (0–6h) dwell** = "home",
most **weekday 9–17 dwell** = "work".

**Step 3 — Build each person's location history** (`sequences.py:19`)
For every (user, hour): the H3 hexagon (r8, ~0.74 km²) where they logged the most points
that hour. Hours with no data stay `UNKNOWN = -1` — honestly marked "unseen", never
filled with guesses.

**Step 4 — Measure how ordered each person is** (`entropy.py`)
Three numbers per user: S_rand (pure chaos baseline), S_unc (independent choices), and
S_actual via Lempel-Ziv compression — see Part 2. Fano's inequality then converts
entropy into a theoretical best-possible accuracy ("the ceiling").

**Step 5 — Mine the "Thursday 15:15" cards** (`routines.py:139`)
Group trips by **(person, weekday, 15-min bucket, origin place, destination place)**.
Keep a card only if it appeared in **>= 3 different weeks** with **>= 50% confidence**.
It's careful counting with strict evidence thresholds.

**Step 6 — The trigger rule** (`routines.py:202`)
Given the current time and where you are: find cards matching (weekday, now ± 15 min,
current place), score by **confidence × stability**, fire if score >= 0.5, show the
route via OSRM.

**Step 7 — Predictors for comparison** (`baselines.py`)
Most-visited cell; most-visited cell per hour-of-week; Markov chains (order 1–3 with
backoff), individual or pooled across everyone. Always trained on the first 80% of each
person's timeline, tested on the last 20% — no future leaking into the past.

### Did H3 (Uber's grid) help?

Yes — essential plumbing:
1. **Discretization**: turned a GPS cloud into countable places. Every analysis
   (entropy's N, Markov states, deep-model classes) needs a finite location set.
2. **Zoom hierarchy**: r9 ≈ 0.1 km² (stop detail) → r8 ≈ 0.74 km² (modeling) →
   r7/r6 (corridors); cells nest, so one stop lives at all scales at once.
3. **Clean vocabulary**: sorted cells → integers 0..N−1 (class labels).

Caveats: r8 creates a 5,000+ class space for only 76 users — that sparsity is part of
why the GNN failed and why raw accuracy numbers look small. Also, H3 nesting is only
~93% exact: parents must be derived via `h3.cell_to_parent` (`stay.py:154`), never by
re-encoding coordinates — a real gotcha handled in this repo.

---

## Part 2 — The compression trick (LZ entropy, `entropy.py:47`)

**The guessing game.** Read someone's hourly location diary aloud to a friend with
*perfect memory* of everything already read. At each point ask: "how far must I read
before my friend says *'whoa — never seen that before'*?" That length is Λ(i).

- **Habitual person**: the friend keeps recognizing long stretches → chunks are LONG
  before anything surprises → ΣΛ large → S = n·log2(n) / ΣΛ is tiny → ceiling near 100%.
- **Erratic person**: every next step surprises immediately → Λ ≈ 1 → S large →
  ceiling near chance.

**Worked example.** Person A's 6-hour diary: `H W H W H G` (home, work, gym):

| i | diary from here | shortest never-seen chunk | Λ(i) |
|---|---|---|---|
| 0 | `H...`     | `H` (nothing seen yet)                          | 1 |
| 1 | `W...`     | `W` (prefix `H` lacks it)                       | 1 |
| 2 | `HWH...`   | `H` seen, `HW` seen, `HWH` **new**              | 3 |
| 3 | `WHW...`   | `W` seen, `WH` seen, `WHG` **new** (prefix `HWH`) | 3 |
| 4 | `HG`       | `H` seen, `HG` **new**                          | 2 |
| 5 | `G`        | `G` **new**                                     | 1 |

ΣΛ = 11 → **S = 6·log2(6) / 11 ≈ 1.41 bits/hour.**

Person B, no habits — never repeats anywhere: `H G P W M C` → every step new,
Λ = 1 each → **S = log2(6) ≈ 2.58 bits** (the maximum for 6 places = pure chaos).

Edge cases in code: one place only → exactly S = 0; a chunk matching everything up to
the diary's end is capped (`entropy.py:57`).

---

## Part 3 — Fano inequality (`entropy.py:77`): bits → speed limit

> Dedicated deep-dive with worked examples: `2026-10-14-fano-inequality-eli5.md`.

**Analogy: a weather forecaster in a desert vs a storm city.** However brilliant the
forecaster, if the weather genuinely contains S bits of randomness, there is a maximum
hit rate no genius can exceed. Fano computes that speed limit from S and N (number of
possible outcomes).

**Where the formula comes from.** The best possible guesser is right with probability
Π, wrong with (1−Π). The person's uncertainty budget S must pay for:
- "Will I be right?" → H(Π) bits;
- "If wrong — where did they actually go?" → (1−Π)·log2(N−1) bits over the other N−1 places.

So **H(Π) + (1−Π)·log2(N−1) = S**, solved for Π by bisection (the left side shrinks as
Π grows; halve the interval 100 times — like the "higher/lower" number-guessing game).

**Plugging in:**
- Person A (3 places, S = 1.41): H(Π) + (1−Π)·1 = 1.41 → **Π ≈ 0.57**. A perfect
  algorithm is right at most ~57% of hours.
- Person B (6 places, S = 2.58): Π = 1/6 ≈ **0.17** — pure chance, no structure to exploit.

Real good GeoLife users → ceiling ~0.64; 93% of users stayed *under* their personal
Π — the speed limit was never violated.

---

## Part 4 — The 15-minute bucket (`routines.py:152`)

The day is sliced into 96 slots. `bucket = (hour×60 + minute) // 15`:

- **15:04** → 904 // 15 = **60**
- **15:12** → 912 // 15 = **60** (same slot as 15:04)
- **15:15** → 915 // 15 = **61** (flips to next slot)

Trips at 15:04 and 15:12 count as "the same time"; the card displays `15:00-15:15`.
Weekday × bucket = 7 × 96 = **672 weekly slots** — "Thursday bucket 60" *is* the
"Thursday 15:15" idea with ±15 min tolerance (humans aren't train-station punctual).

---

## Part 5 — How a card is matched at runtime (`routines.py:202`)

Now = **Thursday 15:07**:

1. My bucket: (15×60+7)//15 = 60.
2. Pull cards where weekday == 3 (Mon=0…Thu=3) and bucket ∈ {60, 61} — now plus the
   next 15 min (lookahead = 1).
3. **Origin check**: last seen cell → its center → nearest of the user's DBSCAN places
   (say *home*) → keep only cards whose origin is *home*. (No location known → any
   origin matches.)
4. Score each survivor by `confidence × stability`; drop < 0.5; rank by score.
5. Top card's destination wins → OSRM draws the route.

Concrete: user 022's card *(Thursday, 15:00–15:15, home → place #3)* matches on all
counts and fires.

---

## Part 6 — Markov chains with order + fallback (`baselines.py:158`)

**Analogy: a parrot with adjustable memory.**
- Order 1: "after Home, where next?"
- Order 2: "after Home→Work, where next?"
- Order 3: "after Gym→Home→Work, where next?"

More memory = sharper question = fewer matching episodes. **Training** (`fit`) builds
all counting tables at once: sliding over the hourly sequence, it tallies every context
length 1..k → what followed, how many times.

**Prediction with fallback** (`predict_ranked`): sharpest question first, degrade
gracefully:

```
context: (Gym, Home, Work)
1. order-3 table: after (Gym, Home, Work)?  seen 5× → always Home → predict Home
   ...never seen:
2. order-2 table: after (Home, Work)?       seen 8× → Gym 5, Home 3 → predict Gym
   ...never seen:
3. order-1 table: after (Work)?             seen 40× → Home 30, Gym 10 → ...
4. frequency: "where does this person just… live?" (most-visited cells,
   padded with everyone's global favorites)
```

Ties break by cell index; top-k is padded with frequency favorites; a context
containing an UNKNOWN hour skips straight to frequency. **Individual vs collective**:
individual = your own counts; collective = one pooled table across all users —
"borrow everyone's experience". Collective won (23%) because individual histories are
thin: shared patterns like "people leave work in the evening" generalize.

---

## Part 7 — Where the assistant's confidence comes from (`routines.py:139`)

Define the **slot** = all of a user's trips from place P, on weekday D, in bucket B
(any destination). Define **g** = those slot trips that went to a specific destination Q.

| quantity | formula | in words |
|---|---|---|
| **support** | distinct weeks in g | how many different weeks this happened — must be >= 3 |
| **confidence** | len(g) / len(slot) | when they left P at this time, what fraction went to Q — must be >= 0.5 |
| **stability** | support ÷ weeks the slot occurred at all (cap 1) | in weeks this slot was alive, how consistently the routine held |
| **trigger score** | confidence × stability | runtime threshold 0.5 |

**Worked example — user 022, Thursdays ~15:00, origin home:**

- Week 1: Thu 15:02 home → **#3** ✓
- Week 2: Thu 15:10 home → **#3** ✓
- Week 3: Thu 14:58 home → office ✗ (slot trip, different destination)
- Week 4: Thu 15:05 home → **#3** ✓
- Week 5: no Thursday departure (slot absent — doesn't count against)

slot = 4 trips / 4 distinct weeks; g = 3 trips / 3 distinct weeks →
support = 3 ✓, confidence = 3/4 = **0.75**, stability = 3/4 = **0.75**,
score = 0.75 × 0.75 = **0.5625** >= 0.5 → **card kept**, fires Thursday 15:07.

The **90% precision** comes from honest replay: `evaluate_trigger` (`routines.py:264`)
hides the last 20% of each user's trips, replays them one by one, fires the trigger,
and counts a *hit* only if the top card's destination equals the true destination.
Strict thresholds (3+ weeks of evidence, majority consistency) mean it rarely speaks —
but when it does, it's almost always right. That's exactly why 154/176 users never saw
it fire: strictness trades coverage for precision.

---

## One-sentence takeaway

The project extracted patterns mostly by *careful counting* — stops → places → hourly
history → recurrences — and the simplest, most evidence-strict methods (Markov,
routine cards) delivered nearly everything the fancy models did.
