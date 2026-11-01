<script>
  import { onEnter, ScrollTrigger } from "../lib/anim.js";
  import { makeMap, addHexes } from "../lib/map.js";

  let { d } = $props();
  const u = $derived(d.user022);

  let mapEl = $state(null);
  let map = $state(null);
  let phase = $state(0); // 0 = r9, 1 = r8
  let loaded = $state(false);

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
      b: "Rolling every small hex up to its parent gives r8 cells of ~0.74 km² — a neighbourhood. Patterns too small to see at block scale (home ↔ two nearby shops) merge into one clean story: home ↔ neighbourhood.",
    },
    {
      t: "One honest gotcha",
      b: "H3 parents don't nest perfectly: encode the same spot independently at r8 and you land in the same parent as the official roll-up only ~93% of the time. We always derive parents the official way — a 7% silent mismatch is how phantom 'trips' are born.",
    },
  ];

  $effect(() => {
    if (!mapEl) return;
    let killed = false;
    let st = null;
    const m = makeMap(mapEl, { center: [116.345, 39.968], zoom: 11.6 });
    m.on("load", () => {
      if (killed) return;
      addHexes(m, "r9", u.hexes.r9, "#5eead4", 0.42);
      addHexes(m, "r8", u.hexes.r8, "#f0abfc", 0.0);
      m.setPaintProperty("r9-line", "line-opacity", 0.5);
      m.setPaintProperty("r8-line", "line-opacity", 0);
      loaded = true;
      st = ScrollTrigger.create({
        trigger: mapEl.closest("section"),
        start: "top top",
        end: "bottom bottom",
        onUpdate: (self) => {
          const p = self.progress;
          const mix = Math.min(1, Math.max(0, (p - 0.4) / 0.3));
          m.setPaintProperty("r9", "fill-opacity", 0.42 * (1 - mix) + 0.06);
          m.setPaintProperty("r9-line", "line-opacity", 0.5 * (1 - mix));
          m.setPaintProperty("r8", "fill-opacity", 0.5 * mix);
          m.setPaintProperty("r8-line", "line-opacity", 0.8 * mix);
          m.easeTo({ zoom: 11.6 - 1.1 * mix, duration: 400 });
        },
      });
    });
    map = m;
    return () => {
      killed = true;
      st?.kill();
      m.remove();
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
        <div class="map" bind:this={mapEl}></div>
        <div class="badge" class:hi={phase === 1}>
          {phase === 1 ? "r8 · ~0.74 km² · neighbourhood" : "r9 · ~0.10 km² · city block"}
        </div>
      </div>
    </div>
    <div class="textcol">
      {#each steps as s, i}
        <div class="tstep" use:onEnter={() => (phase = i >= 2 ? 1 : 0)}>
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
  .badge {
    position: absolute; left: 14px; bottom: 14px;
    background: rgba(11, 15, 20, 0.85); border: 1px solid var(--line);
    color: var(--muted); font-size: 13px; padding: 6px 12px; border-radius: 999px;
  }
  .badge.hi { color: var(--accent-2); border-color: var(--accent-2); }
  .textcol { padding: 0 6px; }
  .tstep { min-height: 58vh; display: flex; flex-direction: column; justify-content: center; }
  .tstep h3 { font-size: 22px; color: var(--ink); }
  .tstep p { color: var(--muted); font-size: 16px; max-width: 44ch; }
  @media (max-width: 880px) {
    .two { grid-template-columns: 1fr; }
    .tstep { min-height: 0; padding: 18px 0; }
  }
</style>
