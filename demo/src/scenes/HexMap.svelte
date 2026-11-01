<script>
  import { ScrollTrigger } from "../lib/anim.js";
  import { makeMap, addHexes, coreBounds, hereApiKey } from "../lib/map.js";

  let { d } = $props();
  const u = $derived(d.user022);
  const hasHere = $derived(!!hereApiKey());

  let mapEl = $state(null);
  let level = $state("auto"); // 'auto' | 'r9' | 'r8' | 'r7'
  let badge = $state("r9");
  let loaded = $state(false);
  let mapFailed = $state(false);
  let autoMix = 0;

  const LEVELS = [
    { id: "r9", name: "blocks r9", area: "r9 · ~0.10 km² · city block", fill: 0.55, dz: 0 },
    { id: "r8", name: "neighbourhood r8", area: "r8 · ~0.74 km² · neighbourhood", fill: 0.6, dz: -1.4 },
    { id: "r7", name: "district r7", area: "r7 · ~5.2 km² · district", fill: 0.65, dz: -2.6 },
  ];

  const steps = [
    {
      t: "Cut the city into hexagons",
      b: "Every stop is pinned to a hexagonal cell from Uber's H3 grid. These are real cells for one Beijing volunteer — small r9 cells, about 0.10 km² each. Roughly a city block.",
    },
    {
      t: "Why hexagons, not squares?",
      b: "A hexagon's six neighbours all touch it at the same length — no corners, no ambiguity about who is 'next door'. A square grid has 8 neighbours, 4 of them weird diagonal ones. Distance in every direction is treated equally.",
    },
    {
      t: "Zoom out one level: r9 → r8",
      b: "Rolling every small hex up to its parent gives r8 cells of ~0.74 km² — a neighbourhood. Patterns too small to see at block scale (home ↔ two nearby shops) merge into one clean story: home ↔ neighbourhood. Try it yourself with the buttons under the map — there is one more level, r7, a whole ~5 km² district.",
    },
    {
      t: "One honest gotcha",
      b: "H3 parents don't nest perfectly: encode the same spot independently at r8 and you land in the same parent as the official roll-up only ~93% of the time. We always derive parents the official way — a 7% silent mismatch is how phantom 'trips' are born.",
    },
  ];

  let map = null; // plain MapLibre handle — never wrap it in $state
  let z0 = 13.4;

  const fillExpr = (base) => [
    "case",
    ["boolean", ["feature-state", "hover"], false],
    Math.min(0.85, base + 0.35),
    base,
  ];

  function setFill(id, fill, line) {
    if (!map || !map.getLayer(id)) return;
    map.setPaintProperty(id, "fill-opacity", fillExpr(fill));
    map.setPaintProperty(`${id}-line`, "line-opacity", line);
  }

  function applyAuto(mix) {
    autoMix = mix;
    badge = mix > 0.5 ? "r8" : "r9";
    setFill("r9", 0.55 * (1 - mix) + 0.05, 0.6 * (1 - mix));
    setFill("r8", 0.6 * mix, 0.85 * mix);
    setFill("r7", 0, 0);
    map?.easeTo({ zoom: z0 - 1.4 * mix, duration: 300 });
  }

  function setLevel(l) {
    level = l;
    if (!map || !loaded) return;
    if (l === "auto") {
      applyAuto(autoMix);
      return;
    }
    const spec = LEVELS.find((x) => x.id === l);
    badge = l;
    for (const lv of LEVELS) setFill(lv.id, lv.id === l ? lv.fill : 0, lv.id === l ? 0.85 : 0);
    map.easeTo({ zoom: z0 + spec.dz, duration: 500 });
  }

  $effect(() => {
    if (!mapEl) return;
    let killed = false;
    let st = null;
    let ro = null;
    let m;
    try {
      m = makeMap(mapEl, { center: [116.345, 39.968], zoom: 11.6 });
    } catch (err) {
      console.warn("map init failed:", err);
      mapFailed = true;
      return;
    }
    m.on("load", () => {
      if (killed) return;
      addHexes(m, "r9", u.hexes.r9, "#5eead4", 0.0);
      addHexes(m, "r8", u.hexes.r8, "#f0abfc", 0.0);
      addHexes(m, "r7", u.hexes.r7, "#fbbf24", 0.0);
      for (const lv of ["r9", "r8", "r7"]) {
        m.setPaintProperty(`${lv}-line`, "line-width", 1.1);
      }
      // Fit where the action is: the core ~90% of stops. Rare far cells stay
      // on the map but must not shrink each hex to a speck.
      // Fit where the action is: the core ~70% of stops within 25 km of home
      // (a single far stop in a fraction cut once stretched the view 900 km).
      const stopPts = u.stops.map((s) => [s.lon, s.lat]);
      const anchorCard = u.cards[0] ?? u.places[0];
      const anchor = [anchorCard.o_lon ?? anchorCard.mean_lon, anchorCard.o_lat ?? anchorCard.mean_lat];
      const cb = coreBounds(stopPts, anchor);
      m.fitBounds(cb, { padding: 36, duration: 0 });
      z0 = m.getZoom();
      setFill("r9", 0.55, 0.6);
      badge = "r9";
      loaded = true;
      st = ScrollTrigger.create({
        trigger: mapEl.closest("section"),
        start: "top top",
        end: "bottom bottom",
        onUpdate: (self) => {
          if (level !== "auto") return;
          const mix = Math.min(1, Math.max(0, (self.progress - 0.4) / 0.3));
          applyAuto(mix);
        },
      });
    });
    map = m;
    ro = new ResizeObserver(() => m.resize());
    ro.observe(mapEl);
    return () => {
      killed = true;
      st?.kill();
      ro?.disconnect();
      m.remove();
      map = null;
    };
  });
</script>

<section class="scene" id="hex">
  <div class="wrap head">
    <span class="kicker" data-reveal>The spatial trick</span>
    <h2 data-reveal>Hexagons give place a shape</h2>
    <p class="lede" data-reveal>
      “Where are you?” needs a unit. Not a street address, not a GPS decimal —
      something that treats every direction equally and rolls up cleanly when
      you zoom out.
    </p>
  </div>

  <div class="grid two">
    <div class="mapcol">
      <div class="sticky">
        <div class="map" bind:this={mapEl}>
          {#if mapFailed}
            <div class="mapfail">
              This browser can’t draw the interactive map (WebGL unavailable) —
              but the idea is simple: every stop of this Beijing volunteer is
              pinned to a hexagonal cell about one city block wide, and seven
              blocks roll up into one neighbourhood cell.
            </div>
          {/if}
        </div>
        <div class="badge">{LEVELS.find((l) => l.id === badge)?.area}</div>
        <div class="lvls">
          <button class:active={level === "auto"} onclick={() => setLevel("auto")}>
            scroll-driven
          </button>
          {#each LEVELS as lv (lv.id)}
            <button class:active={level === lv.id} onclick={() => setLevel(lv.id)}>
              {lv.name}
            </button>
          {/each}
        </div>
        {#if !hasHere}
          <p class="hint">
            Want real streets under the hexagons? Open this page once as
            <code>?here_key=YOUR_KEY</code> — a HERE platform key (free base
            plan). It is stored in your browser only.
          </p>
        {/if}
      </div>
    </div>
    <div class="textcol">
      {#each steps as s, i (s.t)}
        <div class="tstep">
          <h3>{s.t}</h3>
          <p>{s.b}</p>
        </div>
      {/each}
    </div>
  </div>
</section>

<style>
  .head { margin-bottom: 10px; }
  .two {
    grid-template-columns: minmax(0, 1.15fr) minmax(0, 1fr);
    align-items: start;
  }
  .sticky { position: sticky; top: 8vh; }
  .map {
    height: 62vh; min-height: 420px;
    border: 1px solid var(--line); border-radius: 14px; overflow: hidden;
  }
  .mapfail {
    height: 100%; display: flex; align-items: center; justify-content: center;
    padding: 28px; color: var(--muted); font-size: 15px;
    background: var(--bg-2); text-align: center;
  }
  .badge {
    position: absolute; left: 14px; bottom: 58px;
    background: rgba(11, 15, 20, 0.85); border: 1px solid var(--line);
    color: var(--muted); font-size: 13px; padding: 6px 12px; border-radius: 999px;
    pointer-events: none;
  }
  .lvls { display: flex; gap: 6px; flex-wrap: wrap; margin-top: 10px; }
  .lvls button {
    flex: 1; min-width: 100px; padding: 8px 6px; font-size: 13.5px;
    color: var(--muted); background: var(--panel);
    border: 1px solid var(--line); border-radius: 999px; cursor: pointer;
  }
  .lvls button.active {
    color: var(--ink); border-color: var(--accent);
    background: color-mix(in srgb, var(--accent) 10%, var(--panel));
  }
  .hint {
    margin: 10px 2px 0; font-size: 13.5px; color: var(--muted); line-height: 1.5;
  }
  .hint code {
    color: var(--accent); background: var(--bg-2);
    padding: 1px 6px; border-radius: 6px; font-size: 12.5px;
  }
  .textcol { padding: 0 6px; }
  .tstep { min-height: 58vh; display: flex; flex-direction: column; justify-content: center; }
  .tstep h3 { font-size: 22px; color: var(--ink); }
  .tstep p { color: var(--muted); font-size: 16px; max-width: 44ch; }
  @media (max-width: 880px) {
    .two { grid-template-columns: 1fr; }
    .sticky { position: static; }
    .tstep { min-height: 0; padding: 18px 0; }
  }
</style>
