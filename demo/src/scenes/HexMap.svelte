<script>
  // Map-free scene: the hexagon idea as a schematic diagram (7 cells fold into
  // one parent), not a geographic map. No tiles, no WebGL, no keys.
  const R9 = 30; // circumradius of an r9 hexagon in SVG units
  const R8 = Math.sqrt(7) * R9; // area ×7 → radius ×√7
  const R7 = Math.sqrt(49) * R9; // area ×49

  // pointy-top hexagon path (H3 look)
  function hexPath(cx, cy, r) {
    const pt = (a) =>
      `${(cx + r * Math.cos((a * Math.PI) / 180)).toFixed(1)},${(
        cy +
        r * Math.sin((a * Math.PI) / 180)
      ).toFixed(1)}`;
    const angles = [90, 150, 210, 270, 330, 30];
    return `M${pt(angles[0])} L${pt(angles[1])} L${pt(angles[2])} L${pt(angles[3])} L${pt(angles[4])} L${pt(angles[5])} Z`;
  }

  // 7 r9 cells: one centre + six neighbours (pointy-top offsets)
  const r9cells = [
    [0, 0],
    [Math.sqrt(3) * R9, 0],
    [Math.sqrt(3) * R9 * 0.5, 1.5 * R9],
    [-Math.sqrt(3) * R9 * 0.5, 1.5 * R9],
    [-Math.sqrt(3) * R9, 0],
    [-Math.sqrt(3) * R9 * 0.5, -1.5 * R9],
    [Math.sqrt(3) * R9 * 0.5, -1.5 * R9],
  ].map(([dx, dy]) => ({ d: hexPath(360 + dx, 250 + dy, R9) }));

  const legend = [
    {
      chip: "#5eead4",
      name: "r9",
      area: "~0.10 km²",
      what: "city block — every stop lands in exactly one",
    },
    {
      chip: "#f0abfc",
      name: "r8",
      area: "~0.74 km²",
      what: "neighbourhood — 7 blocks fold into one parent",
    },
    {
      chip: "#fbbf24",
      name: "r7",
      area: "~5.2 km²",
      what: "district — the whole city in a handful of cells",
    },
  ];

  const steps = [
    {
      t: "Cut the city into hexagons",
      b: "Every stop is pinned to a hexagonal cell from Uber's H3 grid. The smallest cells we use, r9, cover about 0.10 km² each — roughly a city block. The diagram shows how seven of them fold into one bigger cell. The 2010 paper used phone-tower zones of a few km²; we use H3 hexagons for the same job — nameable boxes for places — at a grain you can pick.",
    },
    {
      t: "Why hexagons, not squares?",
      b: "A hexagon's six neighbours all touch it at the same length — no corners, no ambiguity about who is 'next door'. A square grid has 8 neighbours, 4 of them weird diagonal ones. Distance in every direction is treated equally.",
    },
    {
      t: "Zoom out one level: r9 → r8",
      b: "Rolling every small hex up to its parent gives r8 cells of ~0.74 km² — a neighbourhood. Patterns too small to see at block scale (home ↔ two nearby shops) merge into one clean story: home ↔ neighbourhood. One more level up, r7, is a whole ~5 km² district.",
    },
    {
      t: "One honest gotcha",
      b: "H3 parents don't nest perfectly: encode the same spot independently at r8 and you land in the same parent as the official roll-up only ~93% of the time. We always derive parents the official way — a 7% silent mismatch is how phantom 'trips' are born.",
    },
  ];
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
    <div class="vizcol">
      <div class="sticky" data-reveal>
        <svg viewBox="0 0 720 520" role="img" aria-label="Seven small hexagons folding into one parent hexagon, inside one district hexagon">
          <!-- r7 district -->
          <path d={hexPath(360, 250, R7)} fill="rgba(251,191,36,0.05)" stroke="#fbbf24" stroke-width="2" />
          <!-- r8 parent -->
          <path d={hexPath(360, 250, R8)} fill="rgba(240,171,252,0.08)" stroke="#f0abfc" stroke-width="2" />
          <!-- 7 × r9 cells -->
          {#each r9cells as c, i (i)}
            <path d={c.d} fill="rgba(94,234,212,0.38)" stroke="#5eead4" stroke-width="1.4" />
          {/each}
          <!-- labels with leader lines -->
          <line x1="392" y1="221" x2="560" y2="120" stroke="var(--line)" />
          <text x="566" y="116" class="lab" fill="#5eead4">7 × r9 blocks</text>
          <line x1="425" y1="212" x2="560" y2="196" stroke="var(--line)" />
          <text x="566" y="192" class="lab" fill="#f0abfc">1 × r8 parent</text>
          <line x1="540" y1="330" x2="560" y2="272" stroke="var(--line)" />
          <text x="566" y="268" class="lab" fill="#fbbf24">1 × r7 district</text>
        </svg>
        <div class="legend">
          {#each legend as l (l.name)}
            <div class="lrow">
              <span class="chip" style="background:{l.chip}"></span>
              <b>{l.name}</b>
              <span class="area">{l.area}</span>
              <span class="what">{l.what}</span>
            </div>
          {/each}
        </div>
        <p class="caption">
          <span class="words">
            In words: seven little block-cells roll up into one parent cell —
            the official H3 way, never re-encoded from raw GPS (see the gotcha
            below).
          </span>
        </p>
      </div>
    </div>
    <div class="textcol">
      {#each steps as s (s.t)}
        <div class="tstep" data-reveal>
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
  .viz {
    border: 1px solid var(--line); border-radius: 14px;
    background: var(--panel); padding: 10px;
  }
  svg { width: 100%; height: auto; display: block; }
  .lab { font-size: 14px; font-weight: 600; }
  .legend { margin-top: 6px; display: grid; gap: 8px; }
  .lrow { display: flex; align-items: baseline; gap: 10px; font-size: 14.5px; }
  .lrow b { color: var(--ink); min-width: 2.4ch; }
  .lrow .chip {
    width: 12px; height: 12px; border-radius: 4px; align-self: center;
    flex: none;
  }
  .lrow .area { color: var(--accent); font-variant-numeric: tabular-nums; min-width: 8ch; }
  .lrow .what { color: var(--muted); }
  .caption { margin-top: 12px; }
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
