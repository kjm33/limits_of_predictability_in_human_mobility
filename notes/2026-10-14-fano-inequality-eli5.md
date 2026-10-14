# Fano's Inequality — The Complete ELI5 (2026-10-14)

A dedicated plain-language walkthrough of the Fano predictability ceiling used in this
project (`src/mobility/entropy.py`): where the formula comes from, how it is computed
from raw location sequences step by step (all numbers hand-checked), sanity checks,
worked examples, and its concrete practical impact on the project. Companion to
`2026-10-14-pattern-extraction-eli5.md` and `2026-10-12-results-plain.md`.

---

## 1. The one question Fano answers

Before building *any* prediction model, ask:

> "If I built the **perfect** algorithm — infinite data, infinite intelligence, knowing
> this person's soul — what fraction of hours could it name the right location? What's
> the **speed limit**?"

Fano's inequality computes that speed limit from just two ingredients:

- **N** — how many distinct places the person ever visits,
- **S** — how many *bits of genuine unpredictability* per hour their history contains
  (the entropy: ~0 = robot, log2(N) = chaos).

It returns **Π\*** — the maximum accuracy any algorithm could ever achieve for this
person. It is a **limit, not a model**. Like the speed of light: it doesn't tell you how
to build a fast rocket; it tells you when to stop trying.

**Why this is useful:** predictability is a *property of the human*, measurable directly
from data — *before* any model is built. If someone's ceiling is 60%, no neural network
will ever hit 90% on them, and you know that cheaply and in advance.

## 2. The budget analogy — where the formula comes from

Every hour, reality "picks" where the person goes. Finding out that pick costs **S
bits** — entropy is literally the minimum number of yes/no questions needed, on
average, to pin down the answer. Think of S as the person's **surprise budget**: how
much genuine randomness reality injects each hour.

Now imagine the perfect guesser, right with probability **Π**. Here is an alternative
way to spend bits to learn the truth — a receipt with two lines:

| Receipt line | Cost | Why |
|---|---|---|
| "Was the guess right?" | **H(Π)** bits | a yes/no coin that says "right" with probability Π; its uncertainty is the binary entropy H(Π) |
| "If wrong — which of the *other* places was it?" | **(1−Π)·log2(N−1)** bits | happens with probability (1−Π); if the guess was wrong, the truth is one of the other N−1 places |

Fano's insight (a provable theorem, not a heuristic): **this receipt must be able to pay
for the truth**:

    H(Π) + (1−Π)·log2(N−1) ≥ S

Push the claimed accuracy Π *up*: both lines get *cheaper* (fewer wrongs to identify,
and the yes/no coin becomes more predictable). Claim an accuracy so high that the
receipt total drops **below S**, and you're claiming to buy S bits of truth for less
than S bits — contradiction. The **ceiling Π\*** is exactly where the receipt equals S:

    H(Π*) + (1−Π*)·log2(N−1) = S

That is precisely what `entropy.py:77` solves. One sentence: **the less randomness a
person has (smaller S), the less "error budget" reality can afford, so the more often
even the perfect guesser must be right.**

The only unfamiliar symbol is H(Π), *binary entropy* — "how uncertain is a coin that
lands 'right' with probability Π":

| Π (chance right) | H(Π) | meaning |
|---|---|---|
| 0.5 | 1.00 bit | total coin flip — maximal uncertainty |
| 0.9 | 0.47 bits | almost sure thing — cheap to describe |
| 1.0 | 0 bits | certain — free |

## 3. The full A-to-Z calculation, by hand

**Step A — the raw sequence.** A user's hourly cells for one 12-hour day
(letters = places):

    H W W H P H H W G H W W

**Step B — ingredients.**
- Distinct places: H, W, P, G → **N = 4**. Max possible entropy = log2(4) = 2 bits.
- Frequencies: H ×5, W ×5, P ×1, G ×1 (of 12 hours).

**Step C — entropy S.** (S_unc here because it's hand-computable; the project also
does this with S_actual from the LZ trick — the Fano part is identical.)

- 5/12 of the time H: log2(12/5) = 1.263 → 0.417 × 1.263 = 0.527; same for W → 1.053
- 1/12 each for P and G: log2(12) = 3.585 → 0.083 × 3.585 = 0.299 each → 0.597

    S ≈ 1.65 bits/hour   (within [0, 2] ✓)

**Step D — set up the Fano equation.** N = 4 → log2(N−1) = log2(3) = 1.585:

    H(Π) + (1−Π)·1.585 = 1.65

**Step E — solve by bisection** (exactly what the code does, 100 times,
`entropy.py:95`). The left side *falls* as Π rises: evaluate, keep the half that must
contain the answer, halve again.

| try Π | H(Π) | (1−Π)·1.585 | total | vs S=1.65 | verdict |
|---|---|---|---|---|---|
| 0.25 (=1/N floor) | 0.811 | 1.189 | 2.000 | above | Π must be higher |
| 0.75 | 0.811 | 0.396 | 1.208 | below | too optimistic → lower |
| 0.50 | 1.000 | 0.792 | 1.792 | above | higher |
| 0.60 | 0.971 | 0.634 | 1.605 | below | lower |
| 0.58 | 0.981 | 0.666 | 1.647 | ≈ hit | **Π\* ≈ 0.58** |

Sanity check on the floor row: at Π = 1/N the total is *always* exactly log2(N) —
here 2.000 = log2(4). Built-in self-test.

**Step F — read the result.**

> This person: 4 places, 1.65 bits/hour of randomness → **no algorithm in the universe
> can be right more than ~58% of their hours.** Not a better neural net, not a psychic.

## 4. Sanity-check the extremes

- **The hermit / robot** (one place, or perfectly periodic): S = 0 → forces Π = 1 →
  **ceiling 100%**. Zero randomness, zero unavoidable error. (Code short-circuits the
  constant sequence to exactly S = 0.)
- **The chaos generator** (all N places equally likely, no order): S = log2(N) → pins
  Π = 1/N → **ceiling = dumb luck** (N = 4 → 25%). The entire surprise budget is spent.
- Everyone real lives in between: S ∈ (0, log2 N) → ceiling ∈ (1/N, 1).

## 5. Two people, same N — the ceiling is *personal*

Song et al.'s punchline, with numbers (N = 10 places, log2(9) = 3.17):

**The Commuter** — 10 places but iron habits: S = 1.2 bits.
Solve H(Π) + (1−Π)·3.17 = 1.2 → Π\* ≈ **0.83**. Ten places doesn't hurt if you visit
them *on schedule*.

**The Wanderer** — same 10 places, restless: S = 3.0 bits.
Solve H(Π) + (1−Π)·3.17 = 3.0 → Π\* ≈ **0.35**.

Same vocabulary, wildly different fates: **83% vs 35%**. The ceiling depends on *both*
how many places (N) and how much order (S) — which is why you can't eyeball
predictability from someone's map pins.

## 6. Practical impact on THIS project

1. **It changed the order of questioning.** Instead of "how accurate is my model?", the
   project first asked "what is even *possible* for each human?" — computed per user in
   `entropy.parquet` (Π_rand, Π_unc, Π_actual) before any model was trained.

2. **The three ceilings form a ladder that proves habits exist.** Π_rand = 1/N
   (chance). Π_unc uses only favorite-place frequencies. Π_actual uses full time
   structure. Finding **Π_actual > Π_unc > Π_rand** is a *measured proof* that people's
   movements contain real, exploitable order beyond "they have favorite spots" — the
   reproduction of Song's core claim.

3. **It diagnosed the data instead of blaming the models.** Song's phone-company users:
   ceiling ≈ 93%. GeoLife's logger-on/logger-off users: ceiling ≈ **0.64**. Same math,
   different data. With this spottily-observed data, even a perfect algorithm couldn't
   beat ~64% — the gap to 93% is a property of observation quality, quantified rather
   than hand-waved.

4. **A free honesty audit — "93% of users under their ceiling."** Every real model must
   score ≤ its user's Π\*. After evaluation, the project checked: 93% of users passed.
   If any model had scored *above* its ceiling, that would prove a bug — train/test
   leakage, a leaky feature, or broken metrics. Information theory hands you a unit
   test you didn't have to write.

5. **It defines "headroom" honestly.** Best model (Transformer) = 26%, mean ceiling =
   64% → ~38 points of theoretical headroom. Crucial nuance: Fano is an **upper**
   bound — "nobody can exceed 64%" — it does **not** promise 64% is reachable (bounds
   aren't always tight). Honest reading: plenty of room left, and with ~76 sparse
   users, filling it is unlikely.

6. **It reframes the model comparison.** Frequency 18%, Markov 23%, Transformer 26% —
   all huddle near the *bottom* of a tall ceiling. The models differ mildly in how much
   of the person's structure they capture, and *all* of them leave most of the lawful
   structure on the table. The single most useful strategic fact the Fano analysis
   produced.

## 7. Misconception extinguisher

- **"Π\* is a predictor?"** No. It predicts nothing; it bounds everything. Speed
  limit, not a car.
- **"A smarter model can hit Π\*?"** Not necessarily — the ceiling may be unreachable
  in practice. It tells you when to *stop*, not that the summit exists.
- **"Why log2(N−1), not log2(N)?"** When your guess is *wrong*, the truth is among the
  *other* N−1 places — your (wrong) guess is already eliminated.
- **"More places always lowers the ceiling?"** Not alone — Wanderer vs Commuter: same
  N, 35% vs 83%. Order matters more than vocabulary size.
- **"Where do the three Πs come from?"** Same equation, three entropies plugged in as
  S: S_rand → chance floor; S_unc → favorite-places ceiling; S_actual (LZ-compressed)
  → the true structural ceiling. Only S changes; the machine is the one cranked above.

## One breath

Entropy S is a person's per-hour surprise budget; Fano's equation is the cheapest
possible "receipt" for learning the truth each hour (was the guess right? + if not,
where?); the best achievable accuracy Π\* is exactly where that receipt equals the
budget — and this project used Π\* as a speed limit, a proof that habits exist, a
data-quality diagnosis, a leak detector, and an honest measure of how much room the
models left unused.
