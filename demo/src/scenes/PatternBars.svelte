<script>
  import Section from "../components/Section.svelte";
  import { fmtPct } from "../lib/data.js";

  let { d } = $props();

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
  .threes { grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); }
  .t { padding: 18px; }
  .tnum { font-size: 34px; color: var(--accent-2); margin-bottom: 6px; }
  .t p { color: var(--muted); font-size: 14px; margin: 0; }
  @media (max-width: 760px) {
    .brow { grid-template-columns: 1fr; gap: 4px; text-align: left; }
    .bmeta { text-align: left; }
  }
</style>
