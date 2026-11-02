<script>
  import Section from "../components/Section.svelte";

  let { d } = $props();
  const g = $derived(d.game);

  const palette = {
    home: "#5eead4", work: "#f0abfc", gym: "#fbbf24", shop: "#7dd3fc",
    pub: "#fb7185", park: "#a3e635",
    a: "#7dd3fc", b: "#f0abfc", c: "#fbbf24", d: "#fb7185",
    e: "#a3e635", f: "#5eead4", g: "#c4b5fd", h: "#f9a8d4",
  };

  let revealed = $state(false);

  const personas = $derived([
    { key: "regular", name: "Diary A", who: "the commuter" },
    { key: "wanderer", name: "Diary B", who: "the wanderer" },
  ]);

  // ---- Fano curve: surprise S -> best possible accuracy Pi ------------------
  const F = $derived(d.fano);
  const SMAX = $derived(d.fano.points[d.fano.points.length - 1][0]);
  const W = 560;
  const H = 300;
  const PAD = { l: 46, r: 16, t: 18, b: 40 };
  const sx = (s) => PAD.l + (s / SMAX) * (W - PAD.l - PAD.r);
  const sy = (pi) => H - PAD.b - pi * (H - PAD.t - PAD.b);
  const curve = $derived(F.points.map(([s, pi]) => `${sx(s)},${sy(pi)}`).join(" "));
  const u = $derived(d.user022.pi);

  let slider = $state(22); // index into F.points
  const cur = $derived(F.points[Math.min(slider, F.points.length - 1)]);
  const piWords = (p) =>
    p >= 0.95 ? "nearly always right"
    : p >= 0.8 ? "right 4 times in 5"
    : p >= 0.6 ? "right 3 times in 5"
    : p >= 0.45 ? "about a coin flip with skill"
    : "barely better than chance";

  // ---- per-dataset Pi histograms --------------------------------------------
  const hist = $derived.by(() => {
    const groups = {};
    for (const [k, v] of Object.entries(d.pi)) {
      const key = k.startsWith("yjmob") ? "yjmob" : k;
      (groups[key] ??= []).push(...v);
    }
    const labels = {
      geolife: "GeoLife", brightkite: "Brightkite", fsq_nyc: "Foursquare NYC",
      fsq_tky: "Foursquare Tokyo", gowalla: "Gowalla", yjmob: "YJMob100K",
    };
    const BINS = 10;
    return Object.entries(groups)
      .map(([k, samples]) => {
        const bins = new Array(BINS).fill(0);
        for (const s of samples) bins[Math.min(BINS - 1, Math.floor(s * BINS))]++;
        const top = Math.max(1, ...bins);
        return {
          key: k,
          label: labels[k] ?? k,
          bins: bins.map((b) => b / top),
          n: samples.length,
          hi: samples.filter((s) => s >= 0.8).length / samples.length,
        };
      })
      .sort((a, b) => b.hi - a.hi);
  });
</script>

<Section
  id="entropy"
  kicker="The betting game"
  title="How predictable is a life? Guess first."
  lede="No formulas — just a game. Two people, one week each, shown as colored
  dots (one dot = one place per part of the day). Before we reveal anything:
  which diary could a clever bettor call correctly more often?"
>
  <div class="grid two">
    {#each personas as p (p.key)}
      {@const who = g[p.key]}
      <div class="panel diary" data-reveal>
        <div class="dhead">
          <h3>{p.name}</h3>
          <span class="tag">{revealed ? p.who : "??"}</span>
        </div>
        <div class="dots">
          {#each who.diary.slice(0, 84) as name, i (i)}
            <span class="dot" style="background: {palette[name] ?? '#5c7085'}"
              title={name}></span>
          {/each}
        </div>
        <p class="dsub">first two weeks shown · {who.diary.length} observations total</p>

        {#if revealed}
          <div class="verdict">
            <div class="vrow">
              <span>different places visited</span>
              <b>{who.N}</b>
            </div>
            <div class="vrow">
              <span>surprise per step, ignoring order</span>
              <b>{who.S_unc} bits</b>
            </div>
            <div class="vrow">
              <span>surprise per step, using history</span>
              <b>{who.S_actual} bits</b>
            </div>
            <div class="vrow big">
              <span>best possible guesser's accuracy</span>
              <b>{Math.round(who.Pi_actual * 100)}%</b>
            </div>
          </div>
        {/if}
      </div>
    {/each}
  </div>

  <div class="ctrl" data-reveal>
    {#if !revealed}
      <button class="primary" onclick={() => (revealed = true)}>reveal the numbers</button>
    {:else}
      <p class="after">
        Diary A is the commuter: history cuts its surprise from 1.61 to 0.09 bits
        per step — a perfect guesser could be right <b>99 times in 100</b>.
        Diary B is the wanderer: history barely helps (2.98 → 2.72), capping
        anyone at <b>~37 in 100</b>. The gap between those two numbers — surprise
        with vs without memory — is the entire reason “where will you be next”
        is learnable at all. Real people sit in between; where exactly, the
        panels below show.
      </p>
    {/if}
  </div>

  {#if revealed}
    <div class="fano panel" data-reveal>
      <div class="fleft">
        <h3>From surprise to a ceiling</h3>
        <p class="fsub">
          One referee's rule — <em>Fano's inequality</em> — turns bits into a
          maximum accuracy: for a diary with N = {F.n} places, surprise S fixes
          the best score <em>any</em> algorithm could ever reach — the curve
          below. Our volunteer sits at S = {u.S_actual} bits.
        </p>
        <svg viewBox="0 0 {W} {H}" role="img" aria-label="Fano curve from surprise to best possible accuracy">
          {#each [0, 0.25, 0.5, 0.75, 1] as g (g)}
            <line x1={PAD.l} x2={W - PAD.r} y1={sy(g)} y2={sy(g)} class="grid" />
            <text x={PAD.l - 8} y={sy(g) + 4} class="tick" text-anchor="end">
              {Math.round(g * 100)}%
            </text>
          {/each}
          {#each [0, 2, 4, 6] as t (t)}
            {#if t <= SMAX}
              <text x={sx(t)} y={H - PAD.b + 18} class="tick" text-anchor="middle">{t}</text>
            {/if}
          {/each}
          <text x={(W + PAD.l) / 2} y={H - 6} class="axis" text-anchor="middle">
            surprise per hour S (yes/no questions)
          </text>
          <polyline points={curve} class="curve" />
          <circle cx={sx(cur[0])} cy={sy(cur[1])} r="6" class="curdot" />
          <circle cx={sx(u.S_actual)} cy={sy(u.Pi_actual)} r="6" class="udot" />
          <text x={sx(u.S_actual) + 10} y={sy(u.Pi_actual) - 8} class="ulab">
            volunteer 022 · {Math.round(u.Pi_actual * 100)}%
          </text>
        </svg>
        <div class="slide">
          <input
            type="range" min="0" max={F.points.length - 1} step="1"
            bind:value={slider} aria-label="choose surprise level"
          />
          <div class="readout">
            <b>S = {cur[0].toFixed(2)} bits</b> → ceiling
            <b class="big">{Math.round(cur[1] * 100)}%</b>
            <span>— {piWords(cur[1])}</span>
          </div>
        </div>
      </div>
      <div class="fright">
        <h3>Where real people sit</h3>
        <p class="fsub">
          Everyone's ceiling, one row per dataset (each thin bar = share of
          people; teal = the ≥ 80% club).
        </p>
        {#each hist as h (h.key)}
          <div class="hrow">
            <span class="hlab">{h.label}</span>
            <div class="hbars">
              {#each h.bins as b, j (j)}
                <div
                  class="hb" class:hi={j >= 8}
                  style="height: {Math.max(4, b * 100)}%"
                ></div>
              {/each}
            </div>
            <span class="hval">{Math.round(h.hi * 100)}%</span>
          </div>
        {/each}
        <p class="fnote">
          Dense GPS diaries push people over the 80% line; sparse check-in
          diaries barely get anyone there. The sensing regime — not the city,
          not the year — sets the ceiling.
        </p>
        <p class="fnote sel">
          This is also the selection rule for a proactive agent: measure the
          leftover surprise, convert it with Fano, and spend the effort only
          on people whose ceiling is high — they are the ones for whom
          prediction can work at all. But a ceiling is <em>potential</em>,
          proven in principle; it is not a promise of accuracy. Turning it
          into actual predictions is the next scene's job.
        </p>
      </div>
    </div>
  {/if}
</Section>

<style>
  .two { grid-template-columns: 1fr 1fr; margin-top: 24px; }
  .diary { padding: 20px; }
  .dhead { display: flex; justify-content: space-between; align-items: baseline; }
  .dhead h3 { margin: 0; font-size: 20px; }
  .tag {
    font-size: 12px; font-weight: 700; letter-spacing: 0.08em; text-transform: uppercase;
    color: var(--accent-2);
  }
  .dots {
    display: grid; grid-template-columns: repeat(21, 1fr); gap: 3px;
    margin: 16px 0 8px;
  }
  .dot { width: 100%; aspect-ratio: 1; border-radius: 50%; }
  .dsub { font-size: 12px; color: var(--faint); margin: 0; }
  .verdict { border-top: 1px solid var(--line); margin-top: 14px; padding-top: 10px; }
  .vrow {
    display: flex; justify-content: space-between; padding: 5px 0;
    color: var(--muted); font-size: 15px;
  }
  .vrow b { color: var(--ink); }
  .vrow.big { font-size: 17px; }
  .vrow.big b { color: var(--accent); font-size: 22px; }
  .ctrl { margin-top: 22px; }
  .primary {
    background: color-mix(in srgb, var(--accent) 22%, var(--panel-2));
    border-color: var(--accent); font-weight: 600;
  }
  .after { color: var(--muted); max-width: 60ch; }
  .after b { color: var(--accent); }

  .fano {
    margin-top: 26px; padding: 22px;
    display: grid; grid-template-columns: 1.25fr 1fr; gap: 26px;
  }
  .fano h3 { margin: 0 0 10px; font-size: 17px; color: var(--ink); }
  .fsub { color: var(--muted); font-size: 13.5px; line-height: 1.5; margin: 0 0 12px; }
  .fsub em { color: var(--ink); font-style: normal; font-weight: 600; }
  svg { width: 100%; height: auto; background: var(--bg-2);
        border: 1px solid var(--line); border-radius: 8px; }
  .grid { stroke: var(--line); stroke-width: 0.6; }
  .tick { fill: var(--faint); font-size: 11px; }
  .axis { fill: var(--muted); font-size: 12px; }
  .curve { fill: none; stroke: var(--accent); stroke-width: 2.5; }
  .curdot { fill: var(--accent-2); stroke: var(--bg); stroke-width: 2; }
  .udot { fill: var(--accent); stroke: var(--bg); stroke-width: 2; }
  .ulab { fill: var(--accent); font-size: 12px; font-weight: 700; }
  .slide { display: grid; gap: 8px; margin-top: 14px; }
  .slide input { width: 100%; accent-color: var(--accent-2); }
  .readout { color: var(--muted); font-size: 14px; }
  .readout b { color: var(--ink); }
  .readout b.big { color: var(--accent-2); font-size: 18px; }
  .hrow { display: grid; grid-template-columns: 118px 1fr 44px;
          gap: 10px; align-items: center; margin: 7px 0; }
  .hlab { font-size: 13px; color: var(--muted); text-align: right; }
  .hbars { display: flex; gap: 3px; align-items: end; height: 34px; }
  .hb { flex: 1; background: color-mix(in srgb, var(--muted) 45%, transparent);
        border-radius: 2px 2px 0 0; min-height: 3px; }
  .hb.hi { background: var(--accent); }
  .hval { font-size: 13px; color: var(--accent); font-weight: 700; }
  .fnote { color: var(--muted); font-size: 13px; line-height: 1.5;
           margin: 12px 0 0; border-top: 1px dashed var(--line); padding-top: 10px; }
  .fnote.sel { border-top: none; margin-top: 8px; }
  .fnote em { color: var(--ink); font-style: italic; }
  @media (max-width: 860px) {
    .two { grid-template-columns: 1fr; }
    .fano { grid-template-columns: 1fr; }
  }
</style>
