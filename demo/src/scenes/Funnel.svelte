<script>
  import Section from "../components/Section.svelte";
  import { fmtInt } from "../lib/data.js";

  let { d } = $props();
  const f = $derived(d.funnel);

  const steps = $derived([
    {
      n: f.points,
      label: "raw GPS points",
      how: "Every ping from the loggers — a point every 1–5 seconds.",
    },
    {
      n: f.stops,
      label: "stops",
      how: "A stop = staying within 250 m for at least 10 minutes. Everything else is travel in between.",
    },
    {
      n: f.places,
      label: "places",
      how: "Stops that cluster at the same spot become one place (DBSCAN clustering). 'Home' is simply where the nights pile up.",
    },
    {
      n: f.cohort,
      label: "people with enough data",
      how: "Only people seen often enough can be analyzed — 76 of 182 in GeoLife.",
    },
    {
      n: f.users_with_cards,
      label: "people with weekly routines",
      how: "Same trip, same weekday, same quarter-hour — repeated in at least 3 different weeks.",
    },
    {
      n: f.cards,
      label: "routine cards",
      how: "Each card is one rule like 'Mondays around 15:00, home → the same destination'.",
    },
  ]);
</script>

<Section
  id="funnel"
  kicker="From noise to knowledge"
  title="24.8 million dots become 244 rules"
  lede="Raw location data is a blizzard — one person's day is thousands of nearly
  identical points. Three quiet filters turn the blizzard into structure."
>
  <div class="steps">
    {#each steps as s, i (s.label)}
      <div class="step" data-reveal>
        <div class="bar" style="width: {Math.max(4, 100 - i * 14)}%"></div>
        <div class="row">
          <span class="n num">{fmtInt(s.n)}</span>
          <span class="lab">{s.label}</span>
        </div>
        <p class="how">{s.how}</p>
      </div>
    {/each}
  </div>

  <p class="caption" data-reveal>
    <span class="words">The funnel is honest about loss: 24.8M points → 23,348
    stops → 640 places. But what survives is strong: every rule at the bottom
    held in at least 3 different weeks of real life.</span>
  </p>
</Section>

<style>
  .steps { display: grid; gap: 14px; margin-top: 26px; }
  .step { position: relative; }
  .bar {
    position: absolute; inset: 0 auto 0 0;
    background: linear-gradient(90deg, color-mix(in srgb, var(--accent) 26%, transparent), transparent 96%);
    border-left: 3px solid var(--accent);
    border-radius: 4px;
  }
  .row {
    position: relative; display: flex; align-items: baseline; gap: 14px;
    padding: 6px 12px;
  }
  .n { font-size: clamp(22px, 3.4vw, 34px); color: var(--ink); min-width: 4.4ch; }
  .step:nth-child(n + 5) .n { color: var(--accent-2); }
  .lab { font-size: 17px; color: var(--muted); font-weight: 600; }
  .how {
    position: relative; color: var(--faint); font-size: 14px;
    margin: 0 0 0 12px; max-width: 52ch;
  }
</style>
