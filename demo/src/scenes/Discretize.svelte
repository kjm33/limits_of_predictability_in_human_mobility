<script>
  import Section from "../components/Section.svelte";
  import { cellColor, WEEKDAYS, fmtInt } from "../lib/data.js";
  import { onEnter } from "../lib/anim.js";
  import { onDestroy } from "svelte";

  let { d } = $props();
  const D = $derived(d.user022.discretize);
  const P = $derived(D.points);

  // ---- local projection: fit cell centroids into the SVG viewBox ----------
  const W = 720;
  const H = 380;
  const PAD = 30;
  const proj = $derived.by(() => {
    const lats = D.cells.map((c) => c.lat);
    const lons = D.cells.map((c) => c.lon);
    const latMid = (Math.min(...lats) + Math.max(...lats)) / 2;
    const lonMid = (Math.min(...lons) + Math.max(...lons)) / 2;
    const k = Math.cos((latMid * Math.PI) / 180);
    const raw = D.cells.map((c) => [(c.lon - lonMid) * k, latMid - c.lat]);
    const xs = raw.map((p) => p[0]);
    const ys = raw.map((p) => p[1]);
    const s = Math.min(
      (W - 2 * PAD) / Math.max(1e-6, Math.max(...xs) - Math.min(...xs)),
      (H - 2 * PAD) / Math.max(1e-6, Math.max(...ys) - Math.min(...ys)),
    );
    const at = (lon, lat) => [
      W / 2 + (lon - lonMid) * k * s,
      H / 2 + (latMid - lat) * s,
    ];
    // hex radius from the closest pair of cell centres, kept sane
    let nn = 1e9;
    for (let i = 0; i < raw.length; i++) {
      for (let j = i + 1; j < raw.length; j++) {
        nn = Math.min(nn, Math.hypot(raw[i][0] - raw[j][0], raw[i][1] - raw[j][1]));
      }
    }
    const r = Math.max(3, Math.min(13, 0.58 * (nn === 1e9 ? 20 / s : nn * s)));
    const hex = (lon, lat) => {
      const [x, y] = at(lon, lat);
      return [0, 1, 2, 3, 4, 5]
        .map((a) => {
          const t = (a * Math.PI) / 3;
          return `${(x + r * Math.sin(t)).toFixed(1)},${(y - r * Math.cos(t)).toFixed(1)}`;
        })
        .join(" ");
    };
    return { at, hex };
  });

  // ---- the stream ----------------------------------------------------------
  let idx = $state(0);
  let timer = null;

  const shown = $derived(P.slice(0, idx));
  const touched = $derived(new Set(shown.map((p) => p.c)));
  const cur = $derived(idx > 0 ? P[idx - 1] : null);
  const done = $derived(idx >= P.length);

  const buckets = $derived([...new Set(P.map((p) => p.b))].sort((a, b) => a - b));
  const bucketFill = $derived(buckets.map((b) => shown.filter((p) => p.b === b).length));
  const bucketTot = $derived(buckets.map((b) => P.filter((p) => p.b === b).length));
  const bucketMax = $derived(Math.max(1, ...bucketTot));
  const liveBuckets = $derived(new Set(shown.map((p) => p.b)));

  function stop() {
    if (timer) clearInterval(timer);
    timer = null;
  }
  function start() {
    stop();
    idx = 0;
    timer = setInterval(() => {
      idx = Math.min(idx + 2, P.length);
      if (idx >= P.length) stop();
    }, 24);
  }
  onDestroy(stop);

  const pad2 = (x) => String(x).padStart(2, "0");
  const bLabel = (b) => `${pad2(Math.floor(b / 4))}:${pad2((b % 4) * 15)}`;
</script>

<Section
  id="discretize"
  kicker="The translation"
  title="From the real world to a countable world"
  lede="GPS hands us decimals that never repeat and seconds that never stop.
  Counting needs boxes. Watch one real Monday afternoon — {fmtInt(D.n_raw)}
  raw records — fall into hexagon cells and quarter-hour buckets."
>
  <div class="panel stage" use:onEnter={start}>
    <div class="ticker">
      {#if cur}
        <span class="raw">
          {cur.lat.toFixed(5)}, {cur.lon.toFixed(5)} · {WEEKDAYS[cur.wd]} {bLabel(cur.b)}
        </span>
      {:else}
        <span class="raw dim">waiting for the first record…</span>
      {/if}
      <span class="counter">
        {fmtInt(idx)} / {fmtInt(P.length)} records
      </span>
    </div>

    <div class="viz">
      <svg viewBox="0 0 {W} {H}" role="img" aria-label="Raw GPS points falling into hexagon cells">
        {#each D.cells as c, i (i)}
          <polygon
            points={proj.hex(c.lon, c.lat)}
            class="hx"
            class:lit={touched.has(i)}
            style="--c: {cellColor(i)}"
          />
        {/each}
        {#each P as p, i (i)}
          {@const [x, y] = proj.at(p.lon, p.lat)}
          <circle
            cx={x}
            cy={y}
            r={i === idx - 1 ? 3.4 : 1.6}
            class="pt"
            class:now={i === idx - 1}
            style="fill: {cellColor(p.c)}"
            opacity={i < idx ? 0.85 : 0.13}
          />
        {/each}
      </svg>

      <div class="lane">
        {#each buckets as b, j (b)}
          <div class="slot" class:hot={cur && cur.b === b} class:live={liveBuckets.has(b)}>
            <div class="fill" style="height: {Math.max(3, (bucketFill[j] / bucketMax) * 100)}%"></div>
            <span class="bl">{bLabel(b)}</span>
            <span class="bc">{bucketFill[j]} / {bucketTot[j]}</span>
          </div>
        {/each}
      </div>
    </div>

    <div class="stats">
      <div class="stat">
        <span class="num">{fmtInt(idx)}</span>
        <span>records streamed<br />(of {fmtInt(D.n_raw)} raw)</span>
      </div>
      <div class="stat">
        <span class="num">{touched.size}</span>
        <span>hexagons touched<br />(of {D.n_cells} in this window)</span>
      </div>
      <div class="stat">
        <span class="num">{liveBuckets.size}</span>
        <span>quarter-hours touched<br />(of {D.n_buckets} in this window)</span>
      </div>
      <div class="replay">
        <button class:primary={done || idx === 0} onclick={start}>
          {done ? "replay the 70 minutes" : idx > 0 ? "restart" : "▶ play"}
        </button>
      </div>
    </div>

    {#if done}
      <p class="sum">
        <b>{fmtInt(D.n_raw)} raw GPS records</b> in 70 minutes became
        <b>{D.n_cells} hexagons × {D.n_buckets} quarter-hours</b>. Space stayed
        fluent — a drive crosses a new cell every few seconds — but time stacked
        into just {D.n_buckets} countable boxes. Downstream, every method reads
        only the boxes, never the decimals.
      </p>
    {/if}
  </div>

  <p class="caption" data-reveal>
    <span class="words">Read aloud: this is his actual Monday trip — the same
    15:00–15:15 journey the trigger rule will fire on later. 2,529 records of
    noise, five quarter-hours of story.</span>
  </p>
</Section>

<style>
  .stage { padding: 22px; }
  .ticker {
    display: flex; justify-content: space-between; align-items: baseline;
    font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 14px;
    margin-bottom: 10px;
  }
  .raw { color: var(--accent); }
  .raw.dim { color: var(--faint); }
  .counter { color: var(--faint); font-size: 12px; }
  .viz { display: grid; gap: 14px; }
  svg { width: 100%; height: auto; display: block; background: var(--bg-2);
        border: 1px solid var(--line); border-radius: 8px; }
  .hx { fill: transparent; stroke: var(--line); stroke-width: 0.7; }
  .hx.lit { fill: color-mix(in srgb, var(--c) 26%, transparent);
            stroke: var(--c); stroke-width: 1.1; }
  .pt { stroke: rgba(11, 15, 20, 0.9); stroke-width: 0.5; }
  .pt.now { stroke: var(--ink); }
  .lane { display: flex; gap: 10px; }
  .slot {
    flex: 1; height: 92px; border: 1px solid var(--line); border-radius: 8px;
    background: var(--bg-2); position: relative; overflow: hidden;
    display: grid; align-items: end; padding: 6px; text-align: center;
  }
  .slot .fill {
    position: absolute; left: 0; right: 0; bottom: 0;
    background: linear-gradient(180deg, color-mix(in srgb, var(--accent) 55%, transparent), color-mix(in srgb, var(--accent) 18%, transparent));
    transition: height 0.15s linear;
  }
  .slot.hot { border-color: var(--accent); box-shadow: 0 0 0 1px var(--accent); }
  .slot.live .bl { color: var(--accent); }
  .bl { position: relative; font-size: 13px; font-weight: 700; color: var(--muted); }
  .bc { position: relative; font-size: 11px; color: var(--faint); }
  .stats { display: flex; gap: 26px; align-items: center; margin-top: 16px; flex-wrap: wrap; }
  .stat { display: grid; gap: 3px; }
  .stat .num { font-size: 26px; color: var(--accent); font-weight: 700; }
  .stat span:last-child { font-size: 12px; color: var(--muted); line-height: 1.35; }
  .replay { margin-left: auto; }
  .replay button {
    background: var(--panel-2); border: 1px solid var(--line); color: var(--muted);
    padding: 9px 16px; border-radius: 8px; cursor: pointer; font-size: 14px;
  }
  .replay button.primary { border-color: var(--accent); color: var(--accent); }
  .sum {
    margin: 18px 0 0; color: var(--muted); font-size: 15px; line-height: 1.55;
    border-top: 1px solid var(--line); padding-top: 14px; max-width: 72ch;
  }
  .sum b { color: var(--ink); }
  @media (max-width: 720px) { .ticker { flex-direction: column; gap: 4px; } .stats { gap: 16px; } }
</style>
