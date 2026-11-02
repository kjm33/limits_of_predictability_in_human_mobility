# How routine counting actually works

2026-11-02 · what `mine_routines()` in `src/mobility/routines.py` really computes, in plain language

**Verdict first:** the "pattern detector" is not a model. It is grouping rows in a
table and counting them — filter a person's trips to "leaving this place, on this
weekday, in this quarter-hour", then tally where those trips went. Everything on
the routine cards (support, confidence, stability) falls out of that one tally.

**The tally-sheet analogy.** Picture a sheet with one question at the top —
*"When this person leaves place A on Mondays between 15:00 and 15:15, where do
they go?"* — and a mark next to each destination every time a matching trip is
observed. Three marks beside B and one beside C is all the "learning" there is.

## The precise version (as implemented)

### 1. Trips, not GPS points

Each trip gets an origin place and a destination place
(`_attach_trip_places()` snaps the endpoints to the person's nearest clustered
place). So the counter works on rows like:

```text
user   origin   destination   departure
022    A        B             2026-10-05 15:04
022    A        B             2026-10-12 15:09
022    A        C             2026-10-19 15:02
022    A        B             2026-10-26 15:11
```

(Illustrative rows.) One trip is one row regardless of how many GPS fixes it
contains — a nine-hour workday is one visit, not thirty thousand votes.

### 2. Every departure gets three labels

```python
trips["weekday"]  = dep.dt.weekday                    # 0 = Monday
trips["bucket"]   = (dep.dt.hour*60 + dep.dt.minute) // 15   # 60 = 15:00–15:15
trips["week_key"] = dep.dt.strftime("%G-%V")          # calendar year-week
```

### 3. Two groups, one loop

```python
for (user, weekday, bucket, o_place, d_place), g in trips.groupby(
    ["user", "weekday", "bucket", "o_place", "d_place"]
):
    slot = trips[  # same person, weekday, bucket, origin — ANY destination
        (trips["user"] == user) & (trips["weekday"] == weekday)
        & (trips["bucket"] == bucket) & (trips["o_place"] == o_place)
    ]
    support     = g["week_key"].nunique()          # distinct weeks with A→B
    confidence  = len(g) / len(slot)               # trips to B / all matching trips
    span_weeks  = slot["week_key"].nunique()       # weeks with any matching trip
    stability   = min(support / span_weeks, 1.0)
```

The whole trick is the difference between the two tables:

- **`g`** = matching departures *to one particular destination* (B).
- **`slot`** = matching departures *to any destination*.

For the four illustrative rows: `len(g) = 3` trips to B, `len(slot) = 4` matching
departures, B in 3 distinct weeks, slot spans 4 weeks.

| Metric | Value | Plain meaning |
|---|---|---|
| Support | 3 weeks | B recurred across three separate weeks |
| Confidence | 3/4 = 75% | three quarters of matching *trips* went to B |
| Stability | 3/4 = 75% | B appeared in three quarters of the *weeks* that had any matching departure |

Confidence counts **trips**, stability counts **weeks**: two trips in one week
lift confidence but still count as one week of support. Weeks with no recorded
departure in the slot are not counted against stability.

### 4. Gates

```python
if support < min_support_weeks or confidence < min_confidence:   # 3 weeks, 50%
    continue
```

Groups that pass become routine-card rows. At offer time
(`suggest_destination()`) the agent additionally ranks cards by
`score = confidence × stability` and requires score ≥ 0.5 — a ranking rule, not
a calibrated probability.

## Grounded in this project

- Implementation: `src/mobility/routines.py` — `mine_routines()` (counting),
  `suggest_destination()` (trigger), `evaluate_trigger()` (the 170-of-190
  replay number on the demo page).
- Real example: GeoLife user 022's top card is exactly this shape — Mondays
  15:00–15:15, 3 trips across 3 different weeks, all to the same place
  (confidence 100%). Shown in the demo's "Routines" scene.
- Demo counterpart: the "How a routine gets counted" scene (`demo/src/scenes/
  TripTally.svelte`) walks through the four-row example above.

**Bottom line:** a routine is "from this place, on this weekday, in this
departure window, this destination repeats across weeks" — established by table
grouping, row counts and distinct-week counts, not by any learned model.
