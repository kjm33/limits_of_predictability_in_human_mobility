<script>
  import Section from "../components/Section.svelte";
  import { fmtPct, WEEKDAYS } from "../lib/data.js";

  let { d } = $props();

  const card = $derived(d.user022.cards[0]);
  const geo = $derived(d.datasets.find((r) => r.key === "geolife"));
  const dest = $derived.by(() => {
    const R = 6371;
    const toRad = (x) => (x * Math.PI) / 180;
    const c = card;
    const dl = toRad(c.d_lon - c.o_lon);
    const dp = toRad(c.d_lat - c.o_lat);
    const a =
      Math.sin(dp / 2) ** 2 +
      Math.cos(toRad(c.o_lat)) * Math.cos(toRad(c.d_lat)) * Math.sin(dl / 2) ** 2;
    return 2 * R * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
  });

  const bars = $derived.by(() => {
    const rows = d.datasets.map((r) => ({
      key: r.key,
      label: r.key.startsWith("yjmob") ? "YJMob100K" : r.label,
      pct: r.pct_pattern,
      n: r.users_with_cards,
      cohort: r.cohort_with_cards,
      cards: r.n_cards,
      trig: r.trigger,
      watch: r.volunteered ? "check-ins" : "logged",
    }));
    // merge yjmob rows (both n/a) into one
    const yj = rows.filter((r) => r.key.startsWith("yjmob"));
    const rest = rows.filter((r) => !r.key.startsWith("yjmob"));
    if (yj.length) {
      rest.splice(1, 0, { ...yj[0], label: "YJMob100K", pct: null, n: null });
    }
    return rest.sort((a, b) => (b.pct ?? -1) - (a.pct ?? -1));
  });
</script>

<Section
  id="patterns"
  kicker="The result"
  title="Who has a weekly rhythm?"
  lede="The same detector ran on every dataset. The share of people with a
  machine-findable weekly routine depends on how they were watched — not on
  nationality, city, or year."
>
  <div class="bars">
    {#each bars as b (b.key)}
      <div class="brow" data-reveal>
        <div class="bmeta">
          <span class="bname">{b.label}</span>
          <span class="bwatch">{b.watch}</span>
        </div>
        <div class="btrack">
          {#if b.pct != null}
            <div class="bfill" style="width: {Math.max(1.2, b.pct * 100)}%"></div>
          {/if}
        </div>
        <div class="bval">
          {#if b.pct != null}
            <span class="num">{fmtPct(b.pct, 0)}</span>
            <span class="bsub">{b.n.toLocaleString()} of {b.cohort.toLocaleString()} people</span>
          {:else}
            <span class="na">n/a</span>
            <span class="bsub">grid data — no place detection</span>
          {/if}
        </div>
      </div>
    {/each}
  </div>

  {#if card}
    <div class="panel anatomy" data-reveal>
      <div class="ahead">
        <h3>Anatomy of one firm rule</h3>
        <p class="arule">
          <b>{WEEKDAYS[card.weekday]}s, {card.bucket_str}</b> — leave
          {card.o_label || "his most-visited place"} for
          {card.d_label || `the same spot ${dest.toFixed(1)} km away`}.
          It had to pass three gates before we ever called it a routine:
        </p>
      </div>
      <div class="gates">
        <div class="gate">
          <span class="gnum">{card.support} weeks</span>
          <span class="gname">SUPPORT</span>
          <span class="gval">gate: ≥ 3 separate weeks</span>
          <span class="gword">not a one-off — seen in three different weeks</span>
        </div>
        <div class="gate">
          <span class="gnum">{Math.round(card.confidence * 100)}%</span>
          <span class="gname">CONFIDENCE</span>
          <span class="gval">gate: ≥ 50%</span>
          <span class="gword">every time that weekday × quarter-hour came up,
          it went to the same place</span>
        </div>
        <div class="gate">
          <span class="gnum">{(card.confidence * card.stability).toFixed(2)}</span>
          <span class="gname">SCORE</span>
          <span class="gval">gate: ≥ 0.5 · confidence × stability</span>
          <span class="gword">confident <em>and</em> consistent over time, not
          just once</span>
        </div>
      </div>
      {#if geo && geo.trigger != null}
        <p class="apay">
          And the payoff, on all GeoLife rules at once: when a rule fired, the
          destination it called was right <b>{Math.round(geo.trigger * 100)} times
          in 100</b>.
        </p>
      {/if}
    </div>
  {/if}

  <div class="grid threes" data-reveal>
    <div class="panel t">
      <div class="tnum num">100%</div>
      <p>median confidence of a routine card across all datasets — most rules
      held <em>every</em> time they could fire.</p>
    </div>
    <div class="panel t">
      <div class="tnum num">9 / 10</div>
      <p>when a GeoLife rule fired (“leaving home now, Monday 15:00”), the
      destination was the card's destination 170 of 190 times.</p>
    </div>
    <div class="panel t">
      <div class="tnum num">2%</div>
      <p>Gowalla, the sparsest diary: only 40 of 1,954 people ever repeated a
      trip in the same weekday × quarter-hour twice, let alone 3 weeks.</p>
    </div>
  </div>

  <p class="caption" data-reveal>
    <span class="words">Read aloud: with dense GPS traces we find weekly
    routines in 45 of every 100 analyzable people. With self-reported check-ins
    it's 2–12 of 100 — not because those lives lack rhythm, but because the
    diary has holes exactly where the rhythm lives (“I always get coffee here”
    is a habit that never logs itself at the same minute).</span>
  </p>
</Section>

<style>
  .bars { display: grid; gap: 14px; margin: 26px 0 30px; }
  .brow {
    display: grid; grid-template-columns: 170px minmax(0, 1fr) 210px;
    gap: 14px; align-items: center;
  }
  .bmeta { text-align: right; }
  .bname { font-weight: 700; font-size: 16px; display: block; }
  .bwatch { font-size: 11px; color: var(--faint); text-transform: uppercase; letter-spacing: 0.08em; }
  .btrack {
    height: 26px; background: var(--panel); border: 1px solid var(--line);
    border-radius: 6px; overflow: hidden;
  }
  .bfill {
    height: 100%;
    background: linear-gradient(90deg, var(--accent), color-mix(in srgb, var(--accent) 55%, var(--accent-2)));
  }
  .bval .num { font-size: 24px; color: var(--accent); }
  .bval .bsub, .bsub { display: block; font-size: 12px; color: var(--faint); }
  .na { color: var(--faint); font-size: 20px; font-weight: 700; }
  .anatomy { margin: 26px 0 0; padding: 20px 22px; }
  .ahead h3 { margin: 0 0 8px; font-size: 17px; color: var(--ink); }
  .arule { color: var(--muted); font-size: 14.5px; line-height: 1.55; margin: 0 0 16px;
           max-width: 78ch; }
  .arule b { color: var(--accent); }
  .gates { display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
  .gate {
    border: 1px solid var(--line); border-radius: 10px; padding: 14px 16px;
    display: grid; gap: 3px; background: var(--bg-2);
  }
  .gnum { font-size: 28px; font-weight: 700; color: var(--accent-2); }
  .gname { font-size: 11px; letter-spacing: 0.1em; color: var(--faint); font-weight: 700; }
  .gval { font-size: 12px; color: var(--muted); }
  .gword { font-size: 12.5px; color: var(--muted); line-height: 1.45; }
  .gword em { font-style: normal; color: var(--ink); font-weight: 600; }
  .apay { margin: 16px 0 0; color: var(--muted); font-size: 14px;
          border-top: 1px dashed var(--line); padding-top: 12px; }
  .apay b { color: var(--accent); }
  .threes { grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
  .t { padding: 18px; }
  .tnum { font-size: 34px; color: var(--accent-2); margin-bottom: 6px; }
  .t p { color: var(--muted); font-size: 14px; margin: 0; }
  @media (max-width: 760px) {
    .brow { grid-template-columns: 1fr; gap: 4px; text-align: left; }
    .bmeta { text-align: left; }
  }
</style>
