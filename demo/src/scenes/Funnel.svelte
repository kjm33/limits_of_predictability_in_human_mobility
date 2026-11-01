<script>
  import Section from "../components/Section.svelte";
  import { fmtInt } from "../lib/data.js";

  let { d } = $props();
  const f = $derived(d.funnel);

  // DBSCAN before/after illustration: the same stops, scattered vs clustered.
  const mkCluster = (label, color, pts) => {
    const cx = pts.reduce((a, p) => a + p[0], 0) / pts.length;
    const cy = pts.reduce((a, p) => a + p[1], 0) / pts.length;
    const r = Math.max(...pts.map(([x, y]) => Math.hypot(x - cx, y - cy))) + 9;
    return { label, color, pts, cx, cy, r };
  };
  const clusters = [
    mkCluster("home", "#5eead4", [
      [58, 60], [72, 54], [84, 66], [66, 76], [78, 80], [90, 72],
      [60, 88], [74, 96], [52, 74], [86, 88], [68, 66], [80, 58],
    ]),
    mkCluster("place 2", "#f0abfc", [
      [200, 44], [214, 40], [228, 50], [206, 58], [220, 64],
      [234, 58], [196, 66], [210, 72], [224, 76], [238, 68],
    ]),
    mkCluster("place 3", "#fbbf24", [
      [140, 132], [154, 128], [166, 136], [146, 146], [158, 150],
      [170, 144], [134, 150],
    ]),
  ];
  const noise = [[30, 160], [115, 30], [285, 140], [255, 110], [20, 40]];

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
      how: "Stops that pile up at the same spot become one place — clustered by DBSCAN, explained just below.",
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

  <div class="panel dbscan" data-reveal>
    <h3>How stops become places — clustering with DBSCAN</h3>
    <div class="dviz">
      <figure>
        <svg viewBox="0 0 320 190" role="img" aria-label="Scattered stop dots">
          {#each clusters as c}
            {#each c.pts as [x, y]}<circle cx={x} cy={y} r="3.2" fill="#93a6b8" opacity="0.75" />{/each}
          {/each}
          {#each noise as [x, y]}<circle cx={x} cy={y} r="2.8" fill="#93a6b8" opacity="0.75" />{/each}
        </svg>
        <figcaption>Before — every stop of one person, a scatter of coordinates. No two ever land on the exact same spot.</figcaption>
      </figure>
      <figure>
        <svg viewBox="0 0 320 190" role="img" aria-label="Stops clustered into places">
          {#each clusters as c}
            <circle cx={c.cx} cy={c.cy} r={c.r} fill="none" stroke={c.color} stroke-dasharray="5 4" opacity="0.85" />
            <text x={c.cx} y={c.cy + c.r + 14} text-anchor="middle" fill={c.color} font-size="11">{c.label}</text>
            {#each c.pts as [x, y]}<circle cx={x} cy={y} r="3.2" fill={c.color} />{/each}
          {/each}
          {#each noise as [x, y]}<circle cx={x} cy={y} r="2.8" fill="#7d91a6" opacity="0.3" />{/each}
        </svg>
        <figcaption>After — the same stops as a handful of places. Grey one-offs stay “noise”: never a place.</figcaption>
      </figure>
    </div>
    <p class="dbody">
      DBSCAN is a simple density rule. It walks over one person’s stops and asks:
      does this spot have <strong>at least 5 stops within 300 metres</strong>? If yes,
      those stops merge into one <strong>place</strong> — every stop within reach of
      the group joins it. A stray stop in the middle of nowhere matches nothing and
      is left as noise. That is the whole job of clustering here: it turns
      thousands of near-identical coordinates into a handful of meaningful
      “wheres”. For the Beijing volunteer above: <strong>579 stops collapse into
      13 places</strong>. For all of GeoLife: <strong>23,348 stops → 640 places</strong>.
      Only after this step can the story talk about “home” and “the usual café”
      instead of GPS decimals.
    </p>
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
    position: relative; color: var(--muted); font-size: 14.5px;
    margin: 0 0 0 12px; max-width: 52ch;
  }
  .dbscan { margin-top: 26px; }
  .dbscan h3 { font-size: 19px; margin-bottom: 14px; }
  .dviz {
    display: grid; grid-template-columns: 1fr 1fr; gap: 16px;
    margin-bottom: 14px;
  }
  .dviz figure { margin: 0; }
  .dviz svg {
    width: 100%; height: auto; display: block;
    background: var(--bg-2); border: 1px solid var(--line); border-radius: 10px;
  }
  .dviz figcaption {
    font-size: 13px; color: var(--muted); margin-top: 8px; line-height: 1.45;
  }
  .dbody { color: var(--muted); font-size: 15.5px; max-width: 60ch; margin: 0; }
  @media (max-width: 720px) {
    .dviz { grid-template-columns: 1fr; }
  }
</style>
