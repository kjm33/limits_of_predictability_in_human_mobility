# Markov, Fano and the S measurement — plain-language explanations

2026-11-01 · how the demo's pattern-detection math actually works, told with toy examples

Context: `reports/2026-11-01-demo-website-analysis.md` (demo design),
`efforts/2026-11-01-static-demo-website/` (implementation). All formulas live in
`src/mobility/entropy.py` (S_rand / S_unc / S_actual / Fano Π) and
`src/mobility/routines.py` (support / confidence / stability gates) and
`src/mobility/baselines.py` (Markov orders 1–3, individual + collective).

## 1. The "gzip trick" — how S (surprise) is measured

Read the diary hour by hour and ask at every step: *how far can I keep reading
before I hit something that has literally never happened before?* Long
stretches of "seen it" = low S. Same idea gzip uses to shrink files (we use the
Kontoyiannis 1998 Lempel-Ziv estimator from the Song et al. 2010 Science
paper, not the gzip program itself).

Toy diary `H W H W` (one cell per hour, from `sequences.py` — most-visited
hexagon per hour):

| at hour | question | answer | Λ (stretch) |
|---|---|---|---|
| 1 | has "H" happened before? | no (prefix empty) | 1 |
| 2 | has "W" happened before? | no | 1 |
| 3 | has "H" happened? yes. "HW" from here? yes. Longer? ran out of history | end | 3 |
| 4 | has "W" happened? yes. More? end of diary | end | 2 |

ΣΛ = 7, so S_actual = n·log₂n / ΣΛ = 4·2/7 ≈ **1.14 bits per hour** — "about
one yes/no question per hour still unanswered about this person."

Same 4 hours, three personalities:

| diary | S | in words |
|---|---|---|
| H H H H | 0 | zero unanswered questions — fully routine |
| H W H W | 1.14 | about one question per hour |
| H W C G | 2.0 | two questions per hour — the max, = log₂(4 places) |

S never exceeds log₂N (S_rand). S_unc uses frequencies only and ignores time;
S_actual is the only one that *reads time*. It's an estimator: converges for
long diaries, noisy for a few days — why the cohort filters on observation
length.

## 2. Fano — how the ceiling Π is calculated

One equation, two knowns (S and N), solve for the best possible guessing rate:

    H(Π) + (1 − Π)·log₂(N − 1) = S

Plain reading: H(Π) is the yes/no uncertainty "was the guess right?";
(1−Π)·log₂(N−1) is the cost of saying which of the other N−1 places it actually
was when the guess is wrong. Together they can't exceed the diary's surprise S.

Worked example, N = 4 places, S = 1 bit (log₂3 ≈ 1.585):

| try Π | H(Π) | (1−Π)·1.585 | total | vs S = 1 |
|---|---|---|---|---|
| 0.50 | 1.000 | 0.793 | 1.793 | too big → raise Π |
| 0.80 | 0.722 | 0.317 | 1.039 | still big |
| 0.82 | 0.680 | 0.285 | 0.965 | too small |
| **0.81** | 0.701 | 0.301 | **1.00** | ✓ |

Ceiling ≈ 0.81: *no method on Earth can guess this user's next hour right more
than ~8 of 10 times.* The code (`fano_predictability`) does this try-adjust
loop by bisection, 100 iterations.

Real volunteer 022: N = 121 cells, low S_actual over 4,772 hours → Π = 0.864
("at best ~9 of 10 hours guessable"). Best predictor we built (Markov on
GeoLife) reaches ~0.64 — below his ceiling. Ceiling − model = the demo's
punchline: the math allows more than our models achieve.

## 3. Markov chains — a player, not a referee

A Markov chain is a "from here, where next?" table. From the toy diary
`H H W W W C H H W W`, count every consecutive jump and normalise per row:

| from | → H | → W | → C |
|---|---|---|---|
| H | 0.50 | 0.50 | 0 |
| W | 0 | 0.75 | 0.25 |
| C | 1.00 | 0 | 0 |

Predict by picking the biggest number in the current cell's row. Our pipeline
(`baselines.py`) builds these per user (individual) and pooled over everyone
(collective), looking back 1, 2 or 3 hours (orders 1–3).

Key distinction: Markov is a **player** (one way of guessing). Fano is the
**referee's rulebook** — it looks only at S and N, so it caps every player at
once. Finding: on dense GPS traces (GeoLife) Markov wins; on sparse check-ins
(Foursquare, Gowalla) plain frequency counting wins; nobody beats the ceiling.

## 4. Rule firmness — which habits get to trigger

A routine card claims e.g. "Mondays 15:00–15:15, home → place #3". Two gates
(`mine_routines`, defaults):

- **support** ≥ 3 different weeks (one lucky Monday is not a habit);
- **confidence** ≥ 0.5 — of all the times the weekday+bucket arrived, how often
  the trip actually happened.

Ranking score = confidence × stability (support ÷ weeks the user was watched).
Measured: when a rule fires, it's right ~9 of 10 times (trigger precision 0.895
on GeoLife).
