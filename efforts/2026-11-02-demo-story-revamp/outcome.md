# Outcome — Demo story revamp

**Plain language, what happened:**

## Did

- Reworked the demo from a topic tour into a story arc with a beginning
  (why: Song et al. 2010), a destination (a proactive, on-device navigation
  agent), and an ending that reaches it.
- 12 scenes now, in this order: inspiration hero (paper card + kept project
  stats) → NEW goal scene (proactive agent, on-device framing) → data →
  discretize → funnel → hexagons → time buckets → gzip trick → guessing game
  → routines → results → proactive-agent finale (TriggerDial reworked from
  "The payoff").
- New copy where the user asked: gzip scene now frames gzip as the analogy
  (real method: Lempel-Ziv block counting, as the paper's authors used) and
  adds the low-entropy-as-filter idea; guessing game names Fano's inequality
  as the *selection rule* (spend effort only on high-ceiling people) with an
  explicit "ceiling ≠ accuracy" caveat; hero labels 93% as the paper's
  estimated ceiling for tower data, not achieved accuracy.
- On-device framing throughout uses "the history never has to leave the
  device" wording (not "offline"), with fine print: it's a design goal, not a
  benchmarked claim, and an accepted route still sends origin→destination to
  a routing service.

## Worked

- `cd demo && npm run build` green; `uv run pytest -q` 149 green;
  `uv run ruff check src tests scripts dashboard` clean. New copy verified
  present in the built bundle.
- No Python/data changes needed: the Goal scene is static, the finale reuses
  existing card fields from data.json.

## Didn't

- No new visualizations for the goal scene (a styled notification mockup,
  not a live agent); no on-device benchmark; no routing integration.

## Bottom line

The page now argues a single thesis — regularity is measurable, ceilings are
per-person, and counting is enough to act on — and ends with the agent it
was always about.
