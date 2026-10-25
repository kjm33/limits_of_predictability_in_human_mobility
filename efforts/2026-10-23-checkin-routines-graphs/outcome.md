# Outcome — Check-in routines + graphs (plain language)

## What we did

We ran the two "daily life" pipeline stages — routine mining and transition graphs — on the
four check-in datasets (Foursquare NYC/Tokyo, Gowalla, Brightkite). Until today those stages
had only ever run on GeoLife, so the planned dashboard had no routine cards or random-walk
scores outside Beijing. Two small code fixes were needed first (below), then eight stage runs
plus a GeoLife refresh.

## What worked

- **Venue enrichment makes places meaningful.** Places used to be bare coordinates; now each
  Foursquare place carries its modal venue category. NYC's top place categories come out as
  *Bar / Office / Coffee Shop*; Tokyo's as *Train Station / Subway / Electronics Store* —
  the cities' characters fall out of the data. Gowalla/Brightkite have no venue names in the
  raw data (location IDs only), so their places get empty-but-uniform columns.
- **Graphs scale now.** The random-walk evaluator used to scan the whole hourly panel once
  *per user* — fine for GeoLife's 821k rows, fatal for Gowalla's 231 million (would have
  taken days). One pass over the data instead: all four datasets done in minutes. It also
  stopped scoring users whose predictor was fit on nothing (a subtle garbage-rows bug that
  had quietly polluted even the old GeoLife numbers — GeoLife was re-run and cleaned).
- **Routine cards exist on all datasets**, and the trigger rule holds up remarkably well on
  check-ins: of the routine triggers fired on held-out data, 97%+ hit on Brightkite/Gowalla
  (683/692 and 62/64), similar to GeoLife's 170/190.

| Dataset | Places | Users w/ cards | Cards | Graph users | RW top-1 (hourly) |
|---|---|---|---|---|---|
| GeoLife | 640 | 34 | 244 | 76 | 0.191 |
| fsq_nyc | 706 | 6 | 11 | 62 | 0.148 |
| fsq_tky | 2,101 | 38 | 77 | 494 | 0.140 |
| gowalla | 22,040 | 40 | 72 | 1,954 | 0.058 |
| brightkite | 17,409 | 330 | 914 | 2,757 | 0.156 |

All six output schemas are now byte-identical across the five dataset directories;
tests 119 green, ruff clean; notebooks 04/05 re-executed.

## What didn't

- **Friendship edges are still unused.** Gowalla/Brightkite ship social-network files, but
  the graphs stage builds purely from movement; wiring social ties in is a real feature,
  not a checkbox — logged in BACKLOG.
- **GeoLife-tuned thresholds starve check-in cards.** A card needs the same trip pattern in
  ≥3 weeks at ≥50% confidence — easy for 24/7 GPS tracks, rare for voluntary check-ins
  (NYC: 11 cards). Brightkite's long histories do produce plenty (914). A per-regime
  threshold sensitivity pass is logged in BACKLOG; the dashboard keeps GeoLife as the
  Suggest-flagship regardless.

## Bottom line

The dashboard's data layer is complete: every dataset now tells the same three stories
(entropy/Π, model leaderboards, routines+graphs) with one shared schema, and Foursquare
places even say what they are ("Train Station", not "point 37"). Effort 2 (curating what the
dashboard shows) can start.
