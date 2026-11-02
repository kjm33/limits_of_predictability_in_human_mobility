<script>
  import Section from "../components/Section.svelte";
  import { cellColor, WEEKDAYS } from "../lib/data.js";

  let { d } = $props();
  const u = $derived(d.user022);

  let res = $state(15);
  const grid = $derived(u.grids[String(res)]);
  const maxSup = $derived(Math.max(1, ...grid.support));

  const slotsPerDay = $derived(grid.nb);
  const slotsPerWeek = $derived(7 * grid.nb);

  const filled = $derived(grid.cells.filter((c) => c !== -1).length);
  const steady = $derived(grid.support.filter((s) => s >= 3).length);

  // Clock ticks for the current resolution.
  const ticks = $derived(
    Array.from({ length: slotsPerDay }, (_, i) => i),
  );

  function slotTitle(i) {
    const wd = WEEKDAYS[Math.floor(i / slotsPerDay)];
    const mins = (i % slotsPerDay) * res;
    const hh = String(Math.floor(mins / 60)).padStart(2, "0");
    const mm = String(mins % 60).padStart(2, "0");
    const c = grid.cells[i];
    const cell = c === -1 ? "no data" : u.cells[c].label ?? `cell ${c}`;
    return `${wd} ${hh}:${mm} — usually ${cell} (${grid.support[i]} weeks)`;
  }
</script>

<Section
  id="buckets"
  kicker="The time trick"
  title="Cut time into quarter-hours"
  lede="Where you are means nothing without when you are there. We slice each day
  into buckets — 96 of them at 15 minutes — and ask the same question for every
  weekday: which cell, at this slice, in most weeks?"
>
  <div class="ctrl" data-reveal>
    <span class="clab">bucket size:</span>
    {#each [5, 15, 60] as m (m)}
      <button class:active={res === m} onclick={() => (res = m)}>{m} min</button>
    {/each}
    <span class="cstat num">{slotsPerWeek.toLocaleString()}</span>
    <span class="clab2">slots per week</span>
  </div>

  <div class="viz" data-reveal>
    <div class="clock">
      <svg viewBox="-110 -110 220 220">
        {#each ticks as i (i)}
          {@const mins = i * res}
          {@const ang = (mins / 1440) * 360 - 90}
          <line
            x1={88 * Math.cos((ang * Math.PI) / 180)}
            y1={88 * Math.sin((ang * Math.PI) / 180)}
            x2={100 * Math.cos((ang * Math.PI) / 180)}
            y2={100 * Math.sin((ang * Math.PI) / 180)}
            stroke={grid.cells[2 * slotsPerDay + i] !== -1
              ? cellColor(grid.cells[2 * slotsPerDay + i])
              : "#223041"}
            stroke-width={res === 5 ? 1 : 1.6}
          />
        {/each}
        <circle r="70" fill="none" stroke="#223041" stroke-width="1" />
        <text text-anchor="middle" y="-78" class="cl">00</text>
        <text text-anchor="middle" x="82" y="4" class="cl">06</text>
        <text text-anchor="middle" y="86" class="cl">12</text>
        <text text-anchor="middle" x="-82" y="4" class="cl">18</text>
      </svg>
      <div class="clab3">one weekday (Wed), colored by usual cell</div>
    </div>

    <div class="week">
      <div class="days">
        {#each WEEKDAYS as wd (wd)}<span>{wd}</span>{/each}
      </div>
      <div class="cols" style="--nb: {slotsPerDay}">
        {#each grid.cells as c, i (i)}
          <div
            class="cell"
            style="background: {c === -1 ? 'transparent' : cellColor(c)};
              opacity: {c === -1 ? 0.15 : 0.3 + 0.7 * Math.min(1, grid.support[i] / maxSup)}"
            title={slotTitle(i)}
          ></div>
        {/each}
      </div>
      <div class="axis">
        <span>00</span><span>06</span><span>12</span><span>18</span><span>24</span>
      </div>
    </div>
  </div>

  <p class="caption" data-reveal>
    <span class="words">This is one Beijing volunteer's whole year, folded into
    one week: {filled.toLocaleString()} of {slotsPerWeek.toLocaleString()} slots
    are known, {steady.toLocaleString()} of them repeat in 3+ different weeks
    (same color, same time). 5-minute slices are too nervous — one detour to a
    kiosk shatters them; 60-minute slices blur two after-work habits into one.
    15 minutes is the sweet spot. (Two clocks run through this story: routines
    use these quarter-hours; the predictability analysis coming up uses one
    location per hour — the 2010 paper's choice.)</span>
  </p>
</Section>

<style>
  .ctrl { display: flex; align-items: center; gap: 10px; margin: 24px 0 18px; flex-wrap: wrap; }
  .clab, .clab2 { color: var(--faint); font-size: 14px; }
  .cstat { font-size: 22px; color: var(--accent); margin-left: 10px; }
  .viz {
    display: grid; grid-template-columns: 240px minmax(0, 1fr);
    gap: 28px; align-items: center;
    background: var(--panel); border: 1px solid var(--line);
    border-radius: 14px; padding: 22px;
  }
  .clock { text-align: center; }
  .clock svg { width: 200px; height: 200px; }
  .cl { fill: var(--faint); font-size: 11px; font-family: inherit; }
  .clab3 { font-size: 12px; color: var(--faint); margin-top: 6px; }
  .week { overflow: hidden; }
  .days {
    display: grid; grid-template-rows: repeat(7, 1fr); gap: 3px 0;
    grid-auto-flow: column; margin-bottom: 6px;
  }
  .days span {
    color: var(--faint); font-size: 11px; line-height: 18px; height: 18px;
  }
  .cols {
    display: grid;
    grid-template-columns: repeat(var(--nb), minmax(0, 1fr));
    grid-template-rows: repeat(7, 18px);
    grid-auto-flow: column;
    gap: 3px 1px;
  }
  .cell { border-radius: 2px; min-width: 0; }
  .axis {
    display: flex; justify-content: space-between;
    color: var(--faint); font-size: 11px; margin-top: 6px;
  }
  @media (max-width: 760px) {
    .viz { grid-template-columns: 1fr; }
    .cols { grid-template-rows: repeat(7, 14px); }
  }
</style>
